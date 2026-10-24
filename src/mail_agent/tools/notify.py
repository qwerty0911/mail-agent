"""사용자 알림 카드 아웃박스. Hermes(MCP)가 가져가 Telegram 으로 전달한다."""
import threading
from typing import Any


class Outbox:
    def __init__(self) -> None:
        self._cards: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def post(self, card: dict[str, Any]) -> bool:
        with self._lock:
            self._cards.append(card)
        return True

    def drain(self) -> list[dict[str, Any]]:
        with self._lock:
            out, self._cards = self._cards, []
        return out
