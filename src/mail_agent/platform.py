"""조립 지점: 설정·메일함·Tool Gateway·Registry·에이전트·Supervisor 를 연결한다."""
from dataclasses import dataclass
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from mail_agent.events import Emitter
from mail_agent.gateway.tool_gateway import ToolGateway
from mail_agent.registry.manifest import Registry
from mail_agent.settings import ROOT
from mail_agent.supervisor.graph import Policy, Supervisor, build_agents
from mail_agent.tools.mailbox import MailboxPort
from mail_agent.tools.notify import Outbox


@dataclass
class Platform:
    supervisor: Supervisor
    gateway: ToolGateway
    registry: Registry
    mailbox: MailboxPort
    outbox: Outbox
    emitter: Emitter


def build_platform(mailbox: MailboxPort, llm, checkpointer: BaseCheckpointSaver | None = None,
                   policy: Policy | None = None, persona: str | None = None) -> Platform:
    emitter, outbox, gw = Emitter(), Outbox(), ToolGateway()
    # 도구 등록: 'send' 계열은 의도적으로 없음. capability 는 Manifest 가 에이전트별로 부여한다.
    gw.register_tool("gmail.list_messages", "gmail.read", mailbox.list_messages)
    gw.register_tool("gmail.get_thread", "gmail.read", mailbox.get_thread)
    gw.register_tool("gmail.create_draft", "gmail.draft.create", mailbox.create_draft)
    gw.register_tool("gmail.delete_draft", "gmail.draft.delete", mailbox.delete_draft)
    gw.register_tool("notify.post", "notify", outbox.post)
    gw.set_capabilities("ingest", ["gmail.read"])      # 플랫폼 수집기(LLM 없음)

    registry = Registry.discover()
    if persona is None:
        p = Path(ROOT / "config/persona.md")
        persona = p.read_text() if p.exists() else ""
    agents = build_agents(registry, gw, llm, persona)
    sup = Supervisor(registry, agents, emitter, checkpointer or InMemorySaver(), policy)
    return Platform(sup, gw, registry, mailbox, outbox, emitter)
