"""SQLite 저장소: 처리 이력(멱등성)·메일 뷰·이벤트. API 프로세스와 MCP 프로세스가 같은 파일을 공유(WAL)."""
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._c = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._c.execute("PRAGMA journal_mode=WAL")
        self._c.execute("PRAGMA busy_timeout=5000")
        self._lock = threading.Lock()
        self._c.executescript("""
            CREATE TABLE IF NOT EXISTS mails(mail_id TEXT PRIMARY KEY, run_id TEXT, status TEXT, view TEXT, updated REAL);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, ev TEXT);
            CREATE INDEX IF NOT EXISTS ev_run ON events(run_id);
        """)
        path.chmod(0o600)

    def _q(self, sql: str, args: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._c.execute(sql, args).fetchall()

    def processed(self, mail_id: str) -> bool:
        return bool(self._q("SELECT 1 FROM mails WHERE mail_id=?", (mail_id,)))

    def save_mail(self, mail_id: str, run_id: str, status: str, view: dict[str, Any]) -> None:
        self._q("INSERT INTO mails(mail_id,run_id,status,view,updated) VALUES(?,?,?,?,strftime('%s','now')) "
                "ON CONFLICT(mail_id) DO UPDATE SET status=excluded.status, view=excluded.view, updated=excluded.updated",
                (mail_id, run_id, status, json.dumps(view, ensure_ascii=False)))

    def mails(self) -> list[dict]:
        return [json.loads(r[0]) for r in self._q("SELECT view FROM mails ORDER BY updated DESC")]

    def mail(self, mail_id: str) -> dict | None:
        r = self._q("SELECT view FROM mails WHERE mail_id=?", (mail_id,))
        return json.loads(r[0][0]) if r else None

    def run_id_of(self, mail_id: str) -> str | None:
        r = self._q("SELECT run_id FROM mails WHERE mail_id=?", (mail_id,))
        return r[0][0] if r else None

    def add_event(self, run_id: str, ev: dict) -> None:
        self._q("INSERT INTO events(run_id, ev) VALUES(?,?)", (run_id, json.dumps(ev, ensure_ascii=False)))

    def events_since(self, last_id: int, limit: int = 200) -> list[tuple[int, dict]]:
        return [(r[0], json.loads(r[1])) for r in self._q("SELECT id, ev FROM events WHERE id>? ORDER BY id LIMIT ?", (last_id, limit))]

    def run_events(self, run_id: str) -> list[dict]:
        return [json.loads(r[0]) for r in self._q("SELECT ev FROM events WHERE run_id=? ORDER BY id", (run_id,))]

    def last_event_id(self) -> int:
        r = self._q("SELECT COALESCE(MAX(id),0) FROM events")
        return r[0][0]

    def latest_run_replay(self) -> tuple[int, list[tuple[int, dict]]]:
        """가장 최근 run 의 이벤트(접속 직후 화면 복원용)와 그 마지막 id."""
        r = self._q("SELECT run_id FROM events ORDER BY id DESC LIMIT 1")
        if not r:
            return 0, []
        rows = [(i, json.loads(e)) for i, e in self._q("SELECT id, ev FROM events WHERE run_id=? ORDER BY id", (r[0][0],))]
        return rows[-1][0], rows
