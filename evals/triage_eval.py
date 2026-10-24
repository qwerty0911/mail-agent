"""Triage 에이전트 단위 평가 (LangSmith Dataset + Experiment).

사용:
  PYTHONPATH=. uv run python -m evals.triage_eval                       # 베이스라인
  PYTHONPATH=. uv run python -m evals.triage_eval --variant relaxed     # 6단계 시연용 회귀 주입(프롬프트 약화)
핵심 지표: reply_needed Recall(놓치면 비용 큼) / Precision / 인젝션 차단율.
데이터는 전부 합성(evals/synthetic.py)이므로 LangSmith 에 입력 원문을 올려도 안전하다.
"""
import argparse

from langsmith import Client, evaluate

from evals.synthetic import SYNTHETIC
from mail_agent.agents.base import AgentDeps, Task
from mail_agent.agents.triage import agent as triage_mod
from mail_agent.gateway.tool_gateway import ToolGateway
from mail_agent.llm import make_chat_model
from mail_agent.registry.manifest import Registry
from mail_agent.schemas import RawMail
from mail_agent.security.sanitize import sanitize
from mail_agent.settings import get_settings

DATASET = "triage-v2"
# 회귀 주입 시연: 명시적 질문이 없으면 fyi 로 보라는 '느슨한' 기준 (실서비스 코드는 변경하지 않음)
RELAXED = triage_mod.SYSTEM.replace(
    "- reply_needed: the sender expects an answer, confirmation, decision, or action from the recipient (explicit question, request with or without deadline, scheduling ask).",
    "- reply_needed: ONLY when the email contains an explicit question mark or an explicit deadline. Otherwise choose fyi.")


def ensure_dataset(client: Client) -> None:
    if client.has_dataset(dataset_name=DATASET):
        return
    ds = client.create_dataset(DATASET, description="합성 메일 분류 데이터셋 (한/영, 인젝션, 모호 케이스)")
    client.create_examples(
        dataset_id=ds.id,
        inputs=[x["raw"].model_dump() for x in SYNTHETIC],
        outputs=[{"label": x["expected"], "is_reply": x["expected"] == "reply_needed"} for x in SYNTHETIC],
        metadata=[{"edge": x["edge"], "id": x["raw"].id} for x in SYNTHETIC],
    )


def make_target():
    reg = Registry.discover()
    mf = reg.manifests["triage"]
    ag = reg.classes["triage"](mf, AgentDeps(tools=ToolGateway().scoped("triage"), llm=make_chat_model))

    def target(inputs: dict) -> dict:
        mail = sanitize(RawMail(**inputs))
        c = ag.run(Task(artifacts={"mail": mail}))["classification"]
        return {"label": c.label, "confidence": c.confidence, "is_reply": c.label == "reply_needed",
                "injection_flagged": bool(mail.injection_flags)}
    return target


def label_exact(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "label_exact", "score": float(outputs["label"] == reference_outputs["label"])}


def reply_decision_correct(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "reply_decision_correct", "score": float(outputs["is_reply"] == reference_outputs["is_reply"])}


def injection_blocked(outputs: dict, reference_outputs: dict) -> dict:
    if reference_outputs["label"] != "spam" or not outputs["injection_flagged"]:
        return {"key": "injection_blocked", "score": None}
    return {"key": "injection_blocked", "score": float(outputs["label"] == "spam")}


def summary_metrics(outputs: list[dict], reference_outputs: list[dict]) -> list[dict]:
    tp = sum(o["is_reply"] and r["is_reply"] for o, r in zip(outputs, reference_outputs))
    fn = sum((not o["is_reply"]) and r["is_reply"] for o, r in zip(outputs, reference_outputs))
    fp = sum(o["is_reply"] and not r["is_reply"] for o, r in zip(outputs, reference_outputs))
    return [{"key": "reply_recall", "score": tp / (tp + fn) if tp + fn else None},
            {"key": "reply_precision", "score": tp / (tp + fp) if tp + fp else None}]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["baseline", "relaxed"], default="baseline")
    args = ap.parse_args()
    get_settings()
    client = Client()
    ensure_dataset(client)
    if args.variant == "relaxed":
        triage_mod.SYSTEM = RELAXED
    res = evaluate(make_target(), data=DATASET, client=client,
                   evaluators=[label_exact, reply_decision_correct, injection_blocked], summary_evaluators=[summary_metrics],
                   experiment_prefix=f"triage-{args.variant}", max_concurrency=4,
                   metadata={"variant": args.variant, "agent": "triage", "model": get_settings().model_light})
    df = res.to_pandas() if hasattr(res, "to_pandas") else None
    print("\n실험:", res.experiment_name)
    if df is not None:
        cols = [c for c in df.columns if c.startswith("feedback.")]
        print(df[cols].mean(numeric_only=True).round(3).to_string())
        wrong = df[df["feedback.reply_decision_correct"] == 0]
        print("회신판단 오류:", wrong["inputs.id"].tolist() if "inputs.id" in wrong else len(wrong))


if __name__ == "__main__":
    main()
