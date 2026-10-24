"""웹 대시보드용 HTTP API (+ SSE). 127.0.0.1 바인딩 + X-API-Key 필수."""
import asyncio
import hmac
import json
import os

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from mail_agent.service import MailService, build_service


class ActionIn(BaseModel):
    type: str
    instruction: str | None = None
    reply_needed: bool | None = None


def create_app(service: MailService | None = None, token: str | None = None) -> FastAPI:
    svc = service or build_service()
    api_token = token or (svc.settings.api_token.get_secret_value() if svc.settings and svc.settings.api_token else None) or os.environ.get("API_TOKEN")
    if not api_token:
        raise RuntimeError("API_TOKEN 이 설정되지 않음 — 인증 없는 API 는 기동하지 않는다")
    app = FastAPI(title="mail-agent", docs_url=None, redoc_url=None, openapi_url="/api/openapi.json")

    def auth(x_api_key: str | None = Header(default=None)) -> None:
        if not x_api_key or not hmac.compare_digest(x_api_key, api_token):
            raise HTTPException(401, "unauthorized")

    dep = [Depends(auth)]

    @app.get("/api/mails", dependencies=dep)
    def mails():
        return svc.store.mails()

    @app.get("/api/mails/{mail_id}", dependencies=dep)
    def mail(mail_id: str):
        m = svc.store.mail(mail_id)
        if not m:
            raise HTTPException(404)
        return m

    @app.post("/api/mails/{mail_id}/actions", dependencies=dep)
    def act(mail_id: str, a: ActionIn):
        try:
            return svc.act(mail_id, a.model_dump(exclude_none=True))
        except KeyError:
            raise HTTPException(404)
        except ValueError as e:
            raise HTTPException(409, str(e))

    @app.post("/api/ingest", dependencies=dep)
    def ingest(limit: int = 10):
        return svc.triage_inbox(min(max(limit, 1), 50))

    @app.get("/api/runs/{run_id}", dependencies=dep)
    def run(run_id: str):
        t = svc.run_trace(run_id)
        if not t:
            raise HTTPException(404)
        return t

    @app.get("/api/agents", dependencies=dep)
    def agents():
        return svc.agents()

    @app.get("/api/experiments", dependencies=dep)
    def experiments():
        return []   # 평가 결과 연동은 LangSmith 단계에서 채움

    @app.get("/api/events", dependencies=dep)
    async def events(request: Request):
        async def gen():
            last, replay = svc.store.latest_run_replay()
            yield ": connected\n\n"
            for rid, ev in replay:
                ev["seq"] = rid
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            while not await request.is_disconnected():
                rows = await asyncio.to_thread(svc.store.events_since, last)
                for rid, ev in rows:
                    last = rid
                    ev["seq"] = rid
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if not rows:
                    yield ": ping\n\n"
                    await asyncio.sleep(0.4)
        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app


def main() -> None:  # uv run python -m mail_agent.api.app   (DEMO=1 이면 합성 메일 + 실제 LLM, Gmail 미접속)
    import uvicorn

    from mail_agent.settings import get_settings
    if os.environ.get("DEMO") == "1":
        from evals.synthetic import SYNTHETIC
        from mail_agent.tools.mailbox import FakeMailbox
        s = get_settings()
        s = s.model_copy(update={"data_dir": s.data_dir / "demo"})
        svc = build_service(mailbox=FakeMailbox([x["raw"] for x in SYNTHETIC]), settings=s)
        print("[DEMO] 합성 메일 사용 — Gmail 에 접속하지 않음")
    else:
        svc = build_service()
    uvicorn.run(create_app(svc), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
