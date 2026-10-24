"""Tool Gateway — 모든 외부 도구 호출의 단일 관문.

- 호출자(에이전트 ID)의 Manifest capability 에 도구가 요구하는 권한이 있어야 실행
- 허용/거부 모두 감사 로그에 기록, 거부 시 PermissionDenied
- 등록되지 않은 도구는 호출 불가 → 'send' 계열 도구는 애초에 등록하지 않는다
"""
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class PermissionDenied(Exception):
    pass


@dataclass
class AuditEntry:
    ts: float
    caller: str
    tool: str
    allowed: bool
    detail: str = ""


@dataclass
class ToolGateway:
    _tools: dict[str, tuple[str, Callable[..., Any]]] = field(default_factory=dict)
    _caps: dict[str, set[str]] = field(default_factory=dict)
    audit: list[AuditEntry] = field(default_factory=list)
    on_call: Callable[[AuditEntry], None] | None = None

    def register_tool(self, name: str, capability: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = (capability, fn)

    def set_capabilities(self, caller: str, caps: list[str]) -> None:
        self._caps[caller] = set(caps)

    def tool_names(self) -> list[str]:
        return sorted(self._tools)

    def call(self, caller: str, tool: str, **kwargs: Any) -> Any:
        entry = AuditEntry(time.time(), caller, tool, False)
        try:
            if tool not in self._tools:
                entry.detail = "unknown tool"
                raise PermissionDenied(f"{caller}: 등록되지 않은 도구 {tool}")
            need, fn = self._tools[tool]
            if need not in self._caps.get(caller, set()):
                entry.detail = f"missing capability {need}"
                raise PermissionDenied(f"{caller}: 도구 {tool} 은(는) capability '{need}' 필요")
            entry.allowed = True
            entry.detail = f"capability={need}"
            return fn(**kwargs)
        finally:
            self.audit.append(entry)
            if self.on_call:
                self.on_call(entry)

    def scoped(self, caller: str) -> "ScopedTools":
        return ScopedTools(self, caller)


@dataclass
class ScopedTools:
    """에이전트에게 주입되는 핸들. 호출자 ID 가 고정되어 위조할 수 없다."""
    _gw: ToolGateway
    caller: str

    def call(self, tool: str, **kwargs: Any) -> Any:
        return self._gw.call(self.caller, tool, **kwargs)
