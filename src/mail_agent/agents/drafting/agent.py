from mail_agent.agents.base import DATA_RULE, BaseAgent, Task, email_block
from mail_agent.schemas import ContextPack, DraftResult, MailRef

SYSTEM = f"""You draft an email reply on behalf of the user. Output only the reply body (no subject line).
Rules:
- Write in the same language as the incoming email ("Language" field).
- Answer what was asked. Be concise and polite, following the persona/tone guide.
- NEVER invent facts, prices, dates, availability, or commitments that are not stated in the email, the thread summary, or the user's instruction.
  If the answer needs information you do not have, acknowledge the request and say you will confirm — do not guess.
- Do not include links or email addresses that are not already present in the conversation.
{DATA_RULE}

Persona / tone guide:
{{persona}}"""


class DraftingAgent(BaseAgent):
    def run(self, task: Task):
        mail: MailRef = task.artifacts["mail"]  # type: ignore[assignment]
        ctx: ContextPack = task.artifacts["context"]  # type: ignore[assignment]
        parts = [email_block(mail)]
        if ctx.summary:
            parts.append(f"Earlier thread summary:\n{ctx.summary}")
        if task.previous_draft:
            parts.append(f"Previous draft:\n{task.previous_draft}")
        if task.feedback:
            parts.append("Reviewer found problems — fix them:\n- " + "\n- ".join(task.feedback))
        if task.instruction:
            parts.append(f"User revision request (trusted):\n{task.instruction}")
        llm = self.deps.llm(self.manifest.model_tier).with_structured_output(DraftResult)
        res = llm.invoke([("system", SYSTEM.replace("{persona}", self.deps.persona or "Professional, warm, concise.")),
                          ("human", "\n\n".join(parts))])
        return {"draft": DraftResult(body=res.body.strip())}


AGENT_CLASS = DraftingAgent
