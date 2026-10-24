"""연동 점검. 시크릿 값은 출력하지 않는다. 사용: uv run python scripts/check_setup.py"""
import shutil
import stat
import sys

from mail_agent.settings import GMAIL_SCOPES, ROOT, get_settings

results: list[tuple[str, bool, str]] = []


def check(name: str):
    def deco(fn):
        try:
            msg = fn() or ""
            results.append((name, True, msg))
        except Exception as e:  # noqa: BLE001
            results.append((name, False, f"{type(e).__name__}: {str(e)[:160]}"))
        return fn
    return deco


s = None
try:
    s = get_settings()
    results.append((".env 로드", True, "필수 키 존재"))
except Exception as e:  # noqa: BLE001
    results.append((".env 로드", False, "필수 값 누락 — .env 확인 (값은 출력하지 않음)"))


@check("파일 권한 (.env / .secrets 가 그룹·타인 접근 불가)")
def _perm():
    bad = []
    for p in [ROOT / ".env", *(ROOT / ".secrets").glob("*")]:
        if p.exists() and p.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            bad.append(p.name)
    if bad:
        raise RuntimeError(f"chmod 600 필요: {bad}")


if s:
    @check("LLM 호출 (light / standard)")
    def _llm():
        from mail_agent.llm import make_chat_model
        out = []
        for tier in ("light", "standard"):
            make_chat_model(tier, max_completion_tokens=1024).invoke("ping")
            out.append(tier)
        return f"{s.model_light} · {s.model_standard} OK"

    @check("LangSmith 연결")
    def _ls():
        from langsmith import Client
        c = Client(api_key=s.langsmith_api_key.get_secret_value())
        list(c.list_projects(limit=1))
        return f"project={s.langsmith_project}"

    @check("Gmail 토큰 · 스코프 최소권한")
    def _gmail():
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_file(str(s.gmail_token_file), list(GMAIL_SCOPES))
        extra = set(creds.scopes or []) - set(GMAIL_SCOPES)
        if extra:
            raise RuntimeError(f"과도한 스코프: {sorted(extra)}")
        svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        prof = svc.users().getProfile(userId="me").execute()
        labels = {l["name"] for l in svc.users().labels().list(userId="me").execute().get("labels", [])}
        note = "" if s.gmail_target_label in labels else f" (⚠ 라벨 '{s.gmail_target_label}' 없음 → Gmail에서 생성)"
        return f"{prof['emailAddress'].split('@')[0][:2]}***@… 연결 OK{note}"

@check("Hermes CLI 설치")
def _hermes():
    p = shutil.which("hermes")
    if not p:
        raise RuntimeError("hermes 미설치 (docs/SETUP.md §4)")
    return p

w = max(len(n) for n, _, _ in results)
for n, ok, m in results:
    print(f"{'✓' if ok else '✗'} {n.ljust(w)}  {m}")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
