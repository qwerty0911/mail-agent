import json

import pytest
from fastapi.testclient import TestClient

from mail_agent.api.app import create_app
from mail_agent.service import MailService
from mail_agent.platform import build_platform
from mail_agent.settings import Settings
from mail_agent.store import Store
from mail_agent.tools.mailbox import FakeMailbox
from tests.fakes import happy_llm, mail


@pytest.fixture
def svc(tmp_path):
    mb = FakeMailbox([mail(id="a1"), mail(id="a2", headers={"List-Unsubscribe": "<x>"}, sender="n@x.com", thread="t2")])
    plat = build_platform(mb, happy_llm())
    s = MailService(plat, Store(tmp_path / "t.sqlite"), None)
    s.mb = mb
    return s


@pytest.fixture
def client(svc):
    return TestClient(create_app(svc, token="secret-token")), {"X-API-Key": "secret-token"}


def test_api_requires_token(client):
    c, _ = client
    assert c.get("/api/mails").status_code == 401
    assert c.get("/api/mails", headers={"X-API-Key": "wrong"}).status_code == 401


def test_api_refuses_to_start_without_token(svc, monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        create_app(svc)


def test_ingest_is_idempotent_and_views_match_web_contract(client, svc):
    c, h = client
    out = c.post("/api/ingest", headers=h).json()
    assert {v["status"] for v in out} == {"pending_approval", "skipped"}
    assert c.post("/api/ingest", headers=h).json() == []            # 같은 메일 재처리 안 함
    m = c.get("/api/mails/a1", headers=h).json()
    assert set(m) >= {"id", "runId", "from", "subject", "label", "confidence", "reason", "status", "injectionFlagged", "draft", "body", "language"}
    assert m["draft"]["review"]["passed"] is True and m["draft"]["version"] == 1


def test_action_flow_and_state_guards(client, svc):
    c, h = client
    c.post("/api/ingest", headers=h)
    assert c.post("/api/mails/a1/actions", headers=h, json={"type": "revise"}).status_code == 409      # 지시 없음
    r = c.post("/api/mails/a1/actions", headers=h, json={"type": "revise", "instruction": "더 짧게"}).json()
    assert r["status"] == "pending_approval" and r["draft"]["version"] == 2 and len(svc.mb.drafts) == 1
    assert c.post("/api/mails/a1/actions", headers=h, json={"type": "approve"}).json()["status"] == "approved"
    assert c.post("/api/mails/a1/actions", headers=h, json={"type": "approve"}).status_code == 409    # 이미 종료
    assert c.post("/api/mails/a2/actions", headers=h, json={"type": "classify", "reply_needed": True}).status_code == 409
    assert c.post("/api/mails/nope/actions", headers=h, json={"type": "approve"}).status_code == 404
    assert c.post("/api/mails/a1/actions", headers=h, json={"type": "send"}).status_code in (404, 409)


def test_discard_removes_draft(client, svc):
    c, h = client
    c.post("/api/ingest", headers=h)
    assert c.post("/api/mails/a1/actions", headers=h, json={"type": "discard"}).json()["status"] == "discarded"
    assert not svc.mb.drafts


def test_trace_and_agents_endpoints(client):
    c, h = client
    c.post("/api/ingest", headers=h)
    t = c.get("/api/runs/run-a1", headers=h).json()
    actors = [s["actor"] for s in t["steps"] if s["kind"] == "agent"]
    assert actors == ["triage", "context", "drafting", "reviewer", "delivery"]
    assert any(s["kind"] == "tool" and "gmail.create_draft" in s["title"] for s in t["steps"])      # 도구 호출 감사 노출
    assert any(s["kind"] == "hitl" for s in t["steps"])
    ag = c.get("/api/agents", headers=h).json()
    assert [a["name"] for a in ag] == ["triage", "context", "drafting", "reviewer", "delivery"]


def test_events_do_not_leak_mail_body(client, svc):
    c, h = client
    c.post("/api/ingest", headers=h)
    blob = json.dumps(svc.store.events_since(0, 1000), ensure_ascii=False)
    assert "수정 견적서" not in blob and "회신드리겠습니다" not in blob


def test_mcp_tools_surface():
    import asyncio
    from mail_agent.mcp_server.server import create_server
    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    plat = build_platform(FakeMailbox([mail()]), happy_llm())
    mcp = create_server(MailService(plat, Store(d / "x.sqlite"), None))
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {"triage_inbox", "list_pending", "get_draft", "approve_draft", "revise_draft", "discard_draft", "resolve_classification"}
    assert not [n for n in names if "send" in n]
