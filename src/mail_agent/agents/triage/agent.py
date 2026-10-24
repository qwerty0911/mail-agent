from mail_agent.agents.base import DATA_RULE, BaseAgent, Task, email_block
from mail_agent.schemas import Classification, MailRef

SYSTEM = f"""You triage one incoming email for its recipient and decide whether the recipient must reply.
Labels:
- reply_needed: the sender expects an answer, confirmation, decision, or action from the recipient (explicit question, request with or without deadline, scheduling ask).
- fyi: informational; no response expected (announcements, shared links with no ask, thank-you/acknowledgement notes).
- newsletter: bulk or marketing content.
- spam: unsolicited, phishing, or suspicious.
- auto: automated notifications/receipts/alerts.
Be recall-oriented: when a real person plausibly expects a reply, choose reply_needed. If genuinely ambiguous, pick the most likely label and give a LOW confidence (below 0.6).
confidence is a number from 0 to 1. reason is one short sentence in Korean.
{DATA_RULE}"""


class TriageAgent(BaseAgent):
    def run(self, task: Task):
        mail: MailRef = task.artifacts["mail"]  # type: ignore[assignment]
        # 규칙 선행: 인젝션 의심 메일은 LLM 에 전달하지 않는다
        if mail.injection_flags:
            return {"classification": Classification(label="spam", confidence=0.95,
                    reason=f"프롬프트 인젝션 패턴 탐지({', '.join(mail.injection_flags)}) — LLM 처리 차단")}
        if "list-unsubscribe" in mail.auto_signals or "precedence-bulk" in mail.auto_signals:
            return {"classification": Classification(label="newsletter", confidence=0.97, reason="수신거부 헤더/대량 발송 신호")}
        if "noreply-sender" in mail.auto_signals or "auto-submitted" in mail.auto_signals:
            return {"classification": Classification(label="auto", confidence=0.9, reason="자동 발송 발신자/헤더")}
        llm = self.deps.llm(self.manifest.model_tier).with_structured_output(Classification)
        res = llm.invoke([("system", SYSTEM), ("human", email_block(mail))])
        res.confidence = max(0.0, min(1.0, float(res.confidence)))
        return {"classification": res}


AGENT_CLASS = TriageAgent
