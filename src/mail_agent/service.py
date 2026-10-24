"""애플리케이션 서비스: API(웹 대시보드)와 MCP(Hermes)가 공유하는 유스케이스 계층."""
import contextvars
import sqlite3
from datetime import datetime
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from mail_agent.events import LiveEvent
from mail_agent.platform import Platform, build_platform
from mail_agent.schemas import MailRef
from mail_agent.security.sanitize import sanitize
from mail_agent.settings import GMAIL_SCOPES, Settings, get_settings
from mail_agent.store import Store
from mail_agent.supervisor.graph import Policy
from mail_agent.tools.mailbox import MailboxPort

_current_run: contextvars.ContextVar[str] = contextvars.ContextVar("current_run", default="-")

_STATUS_VIEW = {"approved": "approved", "discarded": "discarded", "skipped": "skipped", "blocked_injection": "skipped"}


class MailService:
    def __init__(self, platform: Platform, store: Store, settings: Settings | None = None) -> None:
        self.p, self.store, self.settings = platform, store, settings
        platform.emitter.subscribe(lambda ev: store.add_event(ev.runId, ev.model_dump(exclude_none=True)))
        # 도구 호출을 실시간 이벤트로 노출 (호출자·capability 포함, 본문은 포함하지 않음)
        platform.gateway.on_call = lambda a: platform.emitter.emit(
            _current_run.get(), "tool_call", "tool_gateway",
            f"{a.tool} · caller={a.caller} · {a.detail} {'✓' if a.allowed else '✗ 거부'}", status="ok" if a.allowed else "error")

    # ---------- 수집/처리 ----------
    def triage_inbox(self, limit: int = 10) -> list[dict]:
        label = self.settings.gmail_target_label if self.settings else None
        raws = self.p.gateway.call("ingest", "gmail.list_messages", label=label, limit=limit)
        out = []
        for raw in raws:
            if self.store.processed(raw.id):
                continue
            out.append(self._run(sanitize(raw)))
        return out

    def _run(self, mail: MailRef) -> dict:
        run_id = f"run-{mail.id}"
        tok = _current_run.set(run_id)
        try:
            res = self.p.supervisor.start(run_id, mail)
        finally:
            _current_run.reset(tok)
        return self._record(mail.id, run_id, res)

    def act(self, mail_id: str, action: dict) -> dict:
        run_id = self.store.run_id_of(mail_id)
        if not run_id:
            raise KeyError(mail_id)
        view = self.store.mail(mail_id) or {}
        kind = action.get("type")
        if kind == "classify":
            payload = {"reply_needed": bool(action.get("reply_needed"))}
            if view.get("status") != "needs_human":
                raise ValueError("분류 확인 대기 상태가 아님")
        elif kind in ("approve", "discard", "revise"):
            payload = {"type": kind, "instruction": action.get("instruction")}
            if view.get("status") != "pending_approval":
                raise ValueError("승인 대기 상태가 아님")
            if kind == "revise" and not (action.get("instruction") or "").strip():
                raise ValueError("수정 요청 내용이 비어 있음")
        else:
            raise ValueError(f"알 수 없는 action: {kind}")
        tok = _current_run.set(run_id)
        try:
            res = self.p.supervisor.resume(run_id, payload)
        finally:
            _current_run.reset(tok)
        return self._record(mail_id, run_id, res)

    # ---------- 뷰 모델 (web/src/api/types.ts 의 Mail 과 동일 형태) ----------
    def _record(self, mail_id: str, run_id: str, res: dict) -> dict:
        view = self._view(run_id, res)
        self.store.save_mail(mail_id, run_id, view["status"], view)
        return view

    @staticmethod
    def _view(run_id: str, res: dict) -> dict:
        a, st = res["artifacts"], res["status"]
        mail, cls = a["mail"], a.get("classification", {})
        itr = res.get("interrupt")
        if itr and itr["type"] == "approval":
            status = "pending_approval"
        elif itr and itr["type"] == "classify":
            status = "needs_human"
        elif st in ("needs_human", "error", "aborted_budget", "no_action"):
            status = "needs_human"
        else:
            status = _STATUS_VIEW.get(st, "needs_human")
        draft = None
        if "draft" in a and "receipt" in a and status in ("pending_approval", "approved"):
            rv = a.get("review", {"passed": False, "issues": []})
            draft = {"id": a["receipt"]["draft_id"], "version": res["state"].get("revisions", 0) + 1,
                     "body": a["draft"]["body"], "review": {"passed": rv["passed"], "issues": rv["issues"]}}
        reason = cls.get("reason", "")
        if st in ("error", "aborted_budget", "no_action"):
            reason = f"처리 중단({st}). " + reason
        return {"id": mail["id"], "runId": run_id, "threadId": mail["thread_id"],
                "from": {"name": mail["sender_name"], "email": mail["sender"]}, "subject": mail["subject"],
                "receivedAt": mail["date"], "language": mail["language"], "body": mail["body"],
                "label": cls.get("label", "fyi"), "confidence": cls.get("confidence", 0.0), "reason": reason,
                "status": status, "injectionFlagged": bool(mail["injection_flags"]), **({"draft": draft} if draft else {})}

    def run_trace(self, run_id: str) -> dict | None:
        evs = [LiveEvent(**e) for e in self.store.run_events(run_id)]
        if not evs:
            return None
        t0 = datetime.fromisoformat(evs[0].ts)
        ms = lambda e: int((datetime.fromisoformat(e.ts) - t0).total_seconds() * 1000)  # noqa: E731
        steps, open_ = [], {}
        kind = {"policy": "policy", "hitl_wait": "hitl", "tool_call": "tool", "run_started": "plan", "run_finished": "plan"}
        for i, e in enumerate(evs):
            if e.type == "node_started":
                open_[e.actor] = (i, e)
            elif e.type == "node_finished" and e.actor in open_:
                j, s = open_.pop(e.actor)
                steps.append({"id": f"s{j}", "actor": e.actor, "kind": "agent", "title": e.message or e.actor,
                              "startMs": ms(s), "durMs": ms(e) - ms(s), "status": e.status or "ok", "model": e.model or s.model, "tokens": e.tokens})
            elif e.type in kind:
                steps.append({"id": f"s{i}", "actor": e.actor, "kind": kind[e.type], "title": e.message,
                              "startMs": ms(e), "durMs": 0, "status": e.status or "ok"})
        steps.sort(key=lambda s: s["startMs"])
        mail_id = run_id.removeprefix("run-")
        return {"id": run_id, "mailId": mail_id, "startedAt": evs[0].ts, "durationMs": ms(evs[-1]), "costUsd": 0.0, "steps": steps}

    def pending_cards(self) -> list[dict]:
        """알림 대기 카드 (Hermes 가 가져가 메신저로 전달). 승인 대기 메일을 DB 기준으로 재구성하므로 재시작에도 안전."""
        return [m for m in self.store.mails() if m["status"] in ("pending_approval", "needs_human")]

    def agents(self) -> list[dict]:
        out = []
        for m in sorted(self.p.registry.manifests.values(), key=lambda m: m.order):
            out.append({"name": m.name, "team": m.team, "description": m.description,
                        "inputSchema": ", ".join(m.requires), "outputSchema": ", ".join(m.produces), "modelTier": m.model_tier,
                        "capabilities": m.capabilities, "riskTier": m.risk_tier,
                        "limits": {"maxSteps": m.limits.max_steps, "maxTokens": m.limits.max_tokens, "timeoutS": m.limits.timeout_s},
                        "evalDataset": m.eval.dataset, "evaluators": m.eval.evaluators, "enabled": m.enabled})
        return out


def build_service(mailbox: MailboxPort | None = None, llm=None, settings: Settings | None = None,
                  policy: Policy | None = None) -> MailService:
    s = settings or get_settings()
    if mailbox is None:
        from mail_agent.tools.mailbox import GmailMailbox
        mailbox = GmailMailbox(s.gmail_token_file, GMAIL_SCOPES)
    if llm is None:
        from mail_agent.llm import make_chat_model
        llm = make_chat_model
    s.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(s.data_dir / "checkpoints.sqlite", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    (s.data_dir / "checkpoints.sqlite").chmod(0o600)
    plat = build_platform(mailbox, llm, checkpointer=SqliteSaver(conn), policy=policy)
    return MailService(plat, Store(s.data_dir / "mail_agent.sqlite"), s)
