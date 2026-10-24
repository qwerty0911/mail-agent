from mail_agent.agents.base import DATA_RULE, BaseAgent, Task
from mail_agent.schemas import ContextPack, MailRef
from mail_agent.security.sanitize import sanitize

SYSTEM = f"""Summarize the earlier messages of an email thread so a writer can reply consistently.
Return a concise factual summary (max 6 lines) in the thread's main language: who said what, open questions, agreed dates/figures.
Do not invent anything. {DATA_RULE}"""


class ContextAgent(BaseAgent):
    def run(self, task: Task):
        mail: MailRef = task.artifacts["mail"]  # type: ignore[assignment]
        thread = self.deps.tools.call("gmail.get_thread", thread_id=mail.thread_id)
        prior = []
        for raw in thread:
            if raw.id == mail.id:
                continue
            ref = sanitize(raw)
            if ref.injection_flags:        # 오염된 이전 메시지는 요약 입력에서 제외
                continue
            prior.append(f"[{ref.sender_name or ref.sender} | {ref.date}]\n{ref.body[:1200]}")
        if not prior:
            return {"context": ContextPack(prior_messages=0, summary="")}
        llm = self.deps.llm(self.manifest.model_tier).with_structured_output(ContextPack)
        text = "<email>\n" + "\n\n---\n\n".join(prior[-6:]) + "\n</email>"
        res = llm.invoke([("system", SYSTEM), ("human", text)])
        return {"context": ContextPack(prior_messages=len(prior), summary=res.summary)}


AGENT_CLASS = ContextAgent
