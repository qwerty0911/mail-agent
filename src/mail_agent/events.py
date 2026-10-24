"""실시간 이벤트 (web/src/api/types.ts 의 LiveEvent 와 동일 스키마). Supervisor·에이전트가 emit, SSE 가 중계."""
import itertools
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

EventType = Literal["run_started", "node_started", "node_finished", "token", "tool_call", "policy", "hitl_wait", "run_finished"]


class LiveEvent(BaseModel):
    seq: int
    ts: str
    runId: str
    type: EventType
    actor: str
    message: str = ""
    status: Literal["ok", "retry", "error", "waiting"] | None = None
    model: str | None = None
    tokens: int | None = None
    delta: str | None = None
    subject: str | None = None


class Emitter:
    def __init__(self) -> None:
        self._seq = itertools.count(1)
        self._sinks: list[Callable[[LiveEvent], None]] = []
        self._lock = threading.Lock()

    def subscribe(self, sink: Callable[[LiveEvent], None]) -> None:
        self._sinks.append(sink)

    def emit(self, run_id: str, type: EventType, actor: str, message: str = "", **extra) -> LiveEvent:
        with self._lock:
            ev = LiveEvent(seq=next(self._seq), ts=datetime.now(timezone.utc).isoformat(), runId=run_id,
                           type=type, actor=actor, message=message, **extra)
        for s in self._sinks:
            try:
                s(ev)
            except Exception:  # noqa: BLE001 — 관측 실패가 본 처리를 막으면 안 된다
                pass
        return ev
