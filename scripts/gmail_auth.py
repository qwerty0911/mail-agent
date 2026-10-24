"""Gmail OAuth 1회 인증. 브라우저가 열리면 본인 계정으로 동의한다.

- 요청 스코프: gmail.readonly + gmail.compose (발송/수정 권한 없음)
- 토큰은 .secrets/ (chmod 600, git 제외)에 저장
- 부여된 스코프가 기대와 다르면(더 넓으면) 토큰을 저장하지 않고 중단
"""
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from mail_agent.settings import GMAIL_SCOPES, get_settings


def main() -> int:
    s = get_settings()
    if not s.gmail_client_secret_file.exists():
        print(f"✗ OAuth 클라이언트 파일 없음: {s.gmail_client_secret_file}\n  docs/SETUP.md 의 Gmail 단계를 먼저 진행하세요.")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(s.gmail_client_secret_file), list(GMAIL_SCOPES))
    creds = flow.run_local_server(host="localhost", port=0, open_browser=True, prompt="consent")

    granted = set(creds.scopes or [])
    extra = granted - set(GMAIL_SCOPES)
    if extra:
        print(f"✗ 기대보다 넓은 스코프가 부여됨: {sorted(extra)} — 토큰 저장 중단")
        return 2

    s.gmail_token_file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(s.gmail_token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(creds.to_json())
    print(f"✓ 토큰 저장 (0600): {s.gmail_token_file}\n  스코프: {sorted(granted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
