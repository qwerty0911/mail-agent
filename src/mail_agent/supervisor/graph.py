"""Root/Mail Supervisor — LangGraph StateGraph.

원칙: Supervisor 는 도구 권한이 없다. 계획(planner)·정책(policy)·산출물 검증·사람 개입(HITL)만 수행하고,
실행은 Registry 의 에이전트가 하며 에이전트는 Tool Gateway 를 통해서만 도구를 쓴다.
"""
from dataclasses import dataclass
from typing import Any, TypedDict

from langchain_core.callbacks import get_usage_metadata_callback
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from mail_agent.agents.base import AgentDeps, BaseAgent, Task
from mail_agent.events import Emitter
from mail_agent.gateway.tool_gateway import ToolGateway
from mail_agent.registry.manifest import Registry
from mail_agent.schemas import ARTIFACT_SCHEMAS, DeliveryReceipt, MailRef


@dataclass
class Policy:
    max_steps: int = 14            # 한 run 의 총 에이전트 실행 상한 (루프·비용 방지)
    max_review_retries: int = 1    # Reviewer 실패 시 자동 재작성 횟수
    max_revisions: int = 3         # 사용자 수정 요청 한도
    confidence_threshold: float = 0.6


class S(TypedDict, total=False):
    run_id: str
    artifacts: dict[str, dict]
    steps: int
    retries: int
    revisions: int
    feedback: list[str]
    instruction: str | None
    previous_draft: str | None
    prev_receipt: dict | None
    route: str
    next: str
    mode: str
    decision: dict | None
    status: str


def build_agents(registry: Registry, gateway: ToolGateway, llm, persona: str) -> dict[str, BaseAgent]:
    agents = {}
    for name, m in registry.manifests.items():
        gateway.set_capabilities(name, m.capabilities)
        agents[name] = registry.classes[name](m, AgentDeps(tools=gateway.scoped(name), llm=llm, persona=persona))
    return agents


class Supervisor:
    def __init__(self, registry: Registry, agents: dict[str, BaseAgent], emitter: Emitter,
                 checkpointer: BaseCheckpointSaver, policy: Policy | None = None) -> None:
        self.registry, self.agents, self.emit, self.policy = registry, agents, emitter, policy or Policy()
        g = StateGraph(S)
        g.add_node("plan", self.plan)
        g.add_node("run_agent", self.run_agent)
        g.add_node("hitl_classify", self.hitl_classify)
        g.add_node("hitl_approval", self.hitl_approval)
        g.add_node("finalize", self.finalize)
        g.add_edge(START, "plan")
        g.add_conditional_edges("plan", lambda s: s["route"],
                                {"run_agent": "run_agent", "hitl_classify": "hitl_classify",
                                 "hitl_approval": "hitl_approval", "finalize": "finalize"})
        for n in ("run_agent", "hitl_classify", "hitl_approval"):
            g.add_edge(n, "plan")
        g.add_edge("finalize", END)
        self.graph = g.compile(checkpointer=checkpointer)

    # ---------- 외부 인터페이스 ----------
    def start(self, run_id: str, mail: MailRef) -> dict:
        self.emit.emit(run_id, "run_started", "supervisor", "새 메일 처리 시작", subject=mail.subject)
        init: S = {"run_id": run_id, "artifacts": {"mail": mail.model_dump()}, "steps": 0, "retries": 0,
                   "revisions": 0, "feedback": [], "instruction": None, "previous_draft": None,
                   "prev_receipt": None, "decision": None}
        return self._invoke(init, run_id)

    def resume(self, run_id: str, value: dict) -> dict:
        return self._invoke(Command(resume=value), run_id)

    def _invoke(self, inp: Any, run_id: str) -> dict:
        cfg = {"configurable": {"thread_id": run_id}, "run_name": "mail_supervisor",
               "tags": ["mail-agent"], "metadata": {"run_id": run_id}}
        out = self.graph.invoke(inp, cfg)
        snap = self.graph.get_state(cfg)
        pending = [i.value for t in snap.tasks for i in t.interrupts]
        return {"status": out.get("status") or ("waiting_human" if pending else "running"),
                "artifacts": out.get("artifacts", {}), "interrupt": pending[0] if pending else None,
                "state": out}

    # ---------- 노드 ----------
    def plan(self, s: S) -> dict:
        rid, arts = s["run_id"], dict(s["artifacts"])
        pol = self.policy

        def done(status: str, **extra) -> dict:
            return {"route": "finalize", "status": status, **extra}

        if s.get("status"):
            return {"route": "finalize"}
        if s["steps"] >= pol.max_steps:
            self.emit.emit(rid, "policy", "supervisor", f"예산 초과({s['steps']}/{pol.max_steps} 스텝) — 중단", status="error")
            return done("aborted_budget")

        cls = arts.get("classification")
        if cls:
            if cls["confidence"] < pol.confidence_threshold and "class_decision" not in arts:
                self.emit.emit(rid, "policy", "supervisor", f"저신뢰 분류({cls['confidence']:.2f} < {pol.confidence_threshold}) — 사람 확인")
                return {"route": "hitl_classify"}
            dec = arts.get("class_decision")
            wants_reply = dec["reply_needed"] if dec else cls["label"] == "reply_needed"
            if not wants_reply:
                return done("blocked_injection" if arts["mail"]["injection_flags"] else "skipped")
            if dec and cls["label"] != "reply_needed":   # 사람이 회신 필요로 정정 → 하위 에이전트 조건 충족
                arts["classification"] = {**cls, "label": "reply_needed", "reason": cls["reason"] + " (사람이 정정)"}

        # Reviewer 결과 평가: 실패 → 자동 재작성(한도 내) / 초과 → 사람 확인 필요
        rv = arts.get("review")
        if rv and not rv["passed"]:
            if s["retries"] < pol.max_review_retries:
                self.emit.emit(rid, "policy", "supervisor", f"검수 실패 — 재작성 {s['retries'] + 1}/{pol.max_review_retries}: " + "; ".join(rv["issues"]), status="retry")
                prev = arts.get("draft", {}).get("body")
                arts.pop("draft", None); arts.pop("review", None)
                return self._pick(s, arts, {"retries": s["retries"] + 1, "feedback": rv["issues"], "previous_draft": prev})
            self.emit.emit(rid, "policy", "supervisor", "검수 재시도 한도 초과 — 사람 확인 필요", status="error")
            return done("needs_human", artifacts=arts)

        # 사용자 결정 처리
        d = s.get("decision")
        if d:
            kind = d.get("type")
            if kind == "approve":
                return done("approved", decision=None)
            if kind == "discard":
                return {"route": "run_agent", "next": "delivery", "mode": "discard", "decision": None}
            if kind == "revise":
                if s["revisions"] >= pol.max_revisions:
                    self.emit.emit(rid, "policy", "supervisor", "수정 요청 한도 초과", status="error")
                    return done("needs_human", decision=None)
                prev_draft = arts.get("draft", {}).get("body")
                prev_receipt = arts.pop("receipt", None)
                arts.pop("draft", None); arts.pop("review", None)
                return self._pick(s, arts, {"revisions": s["revisions"] + 1, "instruction": d.get("instruction"),
                                            "feedback": [], "previous_draft": prev_draft, "prev_receipt": prev_receipt,
                                            "retries": 0, "decision": None})
            return done("needs_human", decision=None)

        if "receipt" in arts:
            return {"route": "hitl_approval", "artifacts": arts}
        return self._pick(s, arts, {})

    def _pick(self, s: S, arts: dict, extra: dict) -> dict:
        cands = self.registry.candidates(arts)
        base = {**extra, "artifacts": arts, "mode": "create"}
        if not cands:
            self.emit.emit(s["run_id"], "policy", "supervisor", "더 실행할 에이전트 없음", status="error")
            return {**base, "route": "finalize", "status": "no_action"}
        return {**base, "route": "run_agent", "next": cands[0].name}

    def run_agent(self, s: S) -> dict:
        rid, name, arts = s["run_id"], s["next"], dict(s["artifacts"])
        mf, agent = self.registry.manifests[name], self.agents[name]
        mode = s.get("mode", "create")
        models: dict[str, Any] = {k: ARTIFACT_SCHEMAS[k].model_validate(v) for k, v in arts.items()}
        if s.get("prev_receipt"):
            models["prev_receipt"] = DeliveryReceipt.model_validate(s["prev_receipt"])
        elif mode == "discard" and "receipt" in arts:
            models["prev_receipt"] = DeliveryReceipt.model_validate(arts["receipt"])
        self.emit.emit(rid, "node_started", name, mf.description[:60], model=mf.model_tier if mf.model_tier != "none" else None)
        task = Task(artifacts=models, feedback=s.get("feedback") or [], instruction=s.get("instruction"),
                    previous_draft=s.get("previous_draft"), mode=mode)  # type: ignore[arg-type]
        try:
            with get_usage_metadata_callback() as cb:
                out = agent.run(task)
            model_name = next(iter(cb.usage_metadata), None)
            tokens = sum(u.get("total_tokens", 0) for u in cb.usage_metadata.values()) or None
            if set(out) != set(mf.produces):
                raise ValueError(f"{name} 산출물 불일치: {sorted(out)} != {mf.produces}")
            for k, v in out.items():
                ARTIFACT_SCHEMAS[k].model_validate(v.model_dump())   # 계약 검증
        except Exception as e:  # noqa: BLE001
            self.emit.emit(rid, "node_finished", name, f"{type(e).__name__}: {str(e)[:120]}", status="error")
            return {"status": "error", "steps": s["steps"] + 1}
        arts.update({k: v.model_dump() for k, v in out.items()})
        summary = self._summ(name, arts)
        self.emit.emit(rid, "node_finished", name, summary, status="ok", model=model_name, tokens=tokens)
        upd: dict = {"artifacts": arts, "steps": s["steps"] + 1, "mode": "create"}
        if mode == "discard":
            upd["status"] = "discarded"
        if name == "delivery" and mode == "create":
            upd["prev_receipt"] = None
        return upd

    @staticmethod
    def _summ(name: str, arts: dict) -> str:
        if name == "triage":
            c = arts["classification"]; return f"label={c['label']} · confidence={c['confidence']:.2f}"
        if name == "reviewer":
            r = arts["review"]; return "통과" if r["passed"] else "실패: " + "; ".join(r["issues"])
        if name == "delivery":
            return f"draft_id={arts['receipt']['draft_id']}"
        if name == "drafting":
            return "초안 완성"
        return "완료"

    def hitl_classify(self, s: S) -> dict:
        rid, cls = s["run_id"], s["artifacts"]["classification"]
        self.emit.emit(rid, "hitl_wait", "supervisor", "저신뢰 분류 — 사용자 판단 대기", status="waiting")
        ans = interrupt({"type": "classify", "classification": cls, "mail_id": s["artifacts"]["mail"]["id"]})
        arts = dict(s["artifacts"]); arts["class_decision"] = {"reply_needed": bool(ans.get("reply_needed"))}
        return {"artifacts": arts}

    def hitl_approval(self, s: S) -> dict:
        rid = s["run_id"]
        self.emit.emit(rid, "hitl_wait", "supervisor", "사용자 승인 대기 (Hermes → Telegram)", status="waiting")
        ans = interrupt({"type": "approval", "receipt": s["artifacts"]["receipt"], "mail_id": s["artifacts"]["mail"]["id"]})
        return {"decision": ans}

    def finalize(self, s: S) -> dict:
        status = s.get("status") or "done"
        self.emit.emit(s["run_id"], "run_finished", "supervisor", f"종료: {status}", status="error" if status in ("error", "aborted_budget", "needs_human") else "ok")
        return {"status": status}
