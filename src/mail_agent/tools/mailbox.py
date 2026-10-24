"""메일함 포트. 구현은 Gmail(실사용)과 Fake(테스트·합성 데이터) 두 가지.

포트에 'send' 가 없다는 것이 무승인 발송 방지의 구조적 보장이다 (tests/test_no_send.py 가 고정).
처리 완료 표시는 Gmail 라벨(modify 권한 필요)이 아니라 로컬 저장소에서 관리한다.
"""
import base64
from email.mime.text import MIMEText
from typing import Protocol

from mail_agent.schemas import RawMail


class MailboxPort(Protocol):
    def list_messages(self, label: str | None, limit: int) -> list[RawMail]: ...
    def get_thread(self, thread_id: str) -> list[RawMail]: ...
    def create_draft(self, thread_id: str, to: str, subject: str, body: str, in_reply_to: str = "") -> str: ...
    def delete_draft(self, draft_id: str) -> None: ...


class FakeMailbox:
    def __init__(self, mails: list[RawMail] | None = None):
        self.mails = list(mails or [])
        self.drafts: dict[str, dict] = {}
        self._n = 0

    def list_messages(self, label, limit):
        return self.mails[:limit]

    def get_thread(self, thread_id):
        return [m for m in self.mails if m.thread_id == thread_id]

    def create_draft(self, thread_id, to, subject, body, in_reply_to=""):
        self._n += 1
        did = f"draft-{self._n}"
        self.drafts[did] = {"thread_id": thread_id, "to": to, "subject": subject, "body": body}
        return did

    def delete_draft(self, draft_id):
        self.drafts.pop(draft_id, None)


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _walk(part: dict, out: dict) -> None:
    mime, body = part.get("mimeType", ""), part.get("body", {})
    if mime == "text/plain" and body.get("data"):
        out["text"] += _decode(body["data"])
    elif mime == "text/html" and body.get("data"):
        out["html"] += _decode(body["data"])
    for sub in part.get("parts", []) or []:
        _walk(sub, out)


def _parse_message(msg: dict) -> RawMail:
    payload = msg.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    out = {"text": "", "html": ""}
    _walk(payload, out)
    from email.utils import parseaddr
    name, addr = parseaddr(headers.get("From", ""))
    return RawMail(
        id=msg["id"], thread_id=msg["threadId"], sender=addr, sender_name=name,
        to=headers.get("To", ""), subject=headers.get("Subject", ""), date=headers.get("Date", ""),
        body_text=out["text"], body_html=out["html"], headers=headers,
        message_id_header=headers.get("Message-ID", headers.get("Message-Id", "")),
    )


class GmailMailbox:
    """gmail.readonly + gmail.compose 만 사용. messages.send / drafts.send 는 호출하지 않는다."""

    def __init__(self, token_file, scopes):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_file(str(token_file), list(scopes))
        self._svc = build("gmail", "v1", credentials=creds, cache_discovery=False)

    def _label_id(self, name: str) -> str | None:
        for lb in self._svc.users().labels().list(userId="me").execute().get("labels", []):
            if lb["name"] == name:
                return lb["id"]
        return None

    def list_messages(self, label, limit):
        kw: dict = {"userId": "me", "maxResults": limit}
        if label:
            lid = self._label_id(label)
            if lid is None:
                return []
            kw["labelIds"] = [lid]
        else:
            kw["labelIds"] = ["INBOX"]
        ids = self._svc.users().messages().list(**kw).execute().get("messages", [])
        return [_parse_message(self._svc.users().messages().get(userId="me", id=m["id"], format="full").execute()) for m in ids]

    def get_thread(self, thread_id):
        t = self._svc.users().threads().get(userId="me", id=thread_id, format="full").execute()
        return [_parse_message(m) for m in t.get("messages", [])]

    def create_draft(self, thread_id, to, subject, body, in_reply_to=""):
        msg = MIMEText(body, "plain", "utf-8")
        msg["To"], msg["Subject"] = to, subject
        if in_reply_to:
            msg["In-Reply-To"] = msg["References"] = in_reply_to
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        d = self._svc.users().drafts().create(userId="me", body={"message": {"raw": raw, "threadId": thread_id}}).execute()
        return d["id"]

    def delete_draft(self, draft_id):
        self._svc.users().drafts().delete(userId="me", id=draft_id).execute()
