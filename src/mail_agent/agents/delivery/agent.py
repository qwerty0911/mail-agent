from mail_agent.agents.base import BaseAgent, Task
from mail_agent.schemas import DeliveryReceipt, DraftResult, MailRef, Review


class DeliveryAgent(BaseAgent):
    """초안 저장(create)·폐기(discard)만 수행한다. 발송 기능은 존재하지 않는다."""

    def run(self, task: Task):
        mail: MailRef = task.artifacts["mail"]  # type: ignore[assignment]
        prev = task.artifacts.get("prev_receipt")
        if task.mode == "discard":
            if prev is not None:
                self.deps.tools.call("gmail.delete_draft", draft_id=prev.draft_id)  # type: ignore[attr-defined]
            return {"receipt": DeliveryReceipt(draft_id=getattr(prev, "draft_id", ""), notified=False)}

        draft: DraftResult = task.artifacts["draft"]  # type: ignore[assignment]
        review: Review = task.artifacts["review"]  # type: ignore[assignment]
        if prev is not None:   # 수정 요청으로 재생성: 이전 초안 제거
            self.deps.tools.call("gmail.delete_draft", draft_id=prev.draft_id)  # type: ignore[attr-defined]
        subject = mail.subject if mail.subject.lower().startswith("re:") else f"Re: {mail.subject}"
        did = self.deps.tools.call("gmail.create_draft", thread_id=mail.thread_id, to=mail.sender,
                                   subject=subject, body=draft.body, in_reply_to=mail.message_id)
        cls = task.artifacts.get("classification")
        ok = self.deps.tools.call("notify.post", card={
            "mail_id": mail.id, "subject": mail.subject, "from": mail.sender_name or mail.sender,
            "label": getattr(cls, "label", ""), "confidence": getattr(cls, "confidence", None),
            "reason": getattr(cls, "reason", ""), "draft_id": did, "draft_preview": draft.body[:400],
            "review_passed": review.passed,
        })
        return {"receipt": DeliveryReceipt(draft_id=did, notified=bool(ok))}


AGENT_CLASS = DeliveryAgent
