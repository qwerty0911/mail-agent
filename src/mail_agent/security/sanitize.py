"""메일 원문 → LLM 에 전달 가능한 MailRef. 결정적(LLM 미사용) 처리.

수행: HTML 제거, 인용·서명 절단, 민감 숫자 마스킹, 길이 제한, 자동발송 신호 추출, 프롬프트 인젝션 패턴 탐지.
주의: 이메일 주소는 마스킹하지 않는다(회신에 필요). 트레이스 마스킹은 observability 계층에서 별도 수행.
"""
import re
import unicodedata
from html.parser import HTMLParser

from mail_agent.schemas import MailRef, RawMail

MAX_BODY_CHARS = 6000

# 강한 신호: AI 에게 직접 내리는 지시·역할 탈취·프롬프트 유출 → 메일을 차단(스팸 처리, LLM 미전달)
STRONG_PATTERNS: list[tuple[str, re.Pattern]] = [(n, re.compile(p, re.I)) for n, p in [
    ("ignore_instructions", r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts?|rules)"),
    ("disregard", r"disregard\s+(all\s+)?(previous|prior|above|your)\s+(instructions|rules)"),
    ("ai_directed", r"(notice|message|note|instruction)s?\s+(to|for)\s+(the\s+)?(ai|assistant|llm|agent|model)"),
    ("ai_addressed", r"(^|\n)\s*(ai\s+assistant|assistant|llm|ai agent)\s*[:,\-]\s*(as|when|please|you must|now|send|forward|change)\b"),
    ("new_system_msg", r"(new|updated)\s+system\s+(message|prompt|instructions?)"),
    ("role_override", r"you\s+are\s+now\s+(a|an|the)\b|act\s+as\s+(a|an)\s+(system|admin|root)"),
    ("system_prompt", r"(reveal|print|show|leak)\s+(your\s+)?(system\s+prompt|instructions)"),
    ("redirect_recipient", r"(change|set|replace|switch)\s+the\s+(recipient|reply-?to|to\s+address)\s+to"),
    ("encoded_exec", r"(decode|execute|run)\s+(this|the\s+following)\s+(base64|command|script|code|payload)"),
    ("ko_ignore", r"(앞|이전|위|기존)[의\s]*(지시|명령|지침|프롬프트)[가-힣]*\s*[은는을를]?\s*(모두\s*)?(무시|잊)"),
    ("ko_role_override", r"(지금부터|이제부터)\s*(너는|당신은|넌)\s*.{0,12}(모드|관리자|시스템|AI)"),
    ("ko_ai_directed", r"(AI|에이전트|어시스턴트|인공지능)\s*(에게|님께)\s*.{0,20}(전달|전송|포워딩|유출|보내)"),
]]
# 약한 신호: 정상 업무 메일에서도 나올 수 있는 표현 → 차단하지 않고 표시만 한다(LLM 은 도구가 없고 Reviewer 가 추가 점검)
WEAK_PATTERNS: list[tuple[str, re.Pattern]] = [(n, re.compile(p, re.I)) for n, p in [
    ("exfiltrate", r"(forward|send|email)\s+(the\s+)?(last|all|every|previous)\s+\d*\s*(emails|messages|threads)\b"),
    ("ko_exfiltrate", r"(최근|모든|지난)\s*\d*\s*(개의\s*)?(메일|이메일)[을를]?\s*.{0,15}(전달|전송|포워딩|보내)"),
    ("ko_broadcast", r"(모든|전체)\s*(연락처|주소록)\S*\s*.{0,10}(전달|전송|보내)"),
]]
_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad]")


def _norm(text: str) -> str:
    """탐지용 정규화: NFKC(전각→반각), 비가시 문자 제거, 공백 정리. 원문은 변경하지 않는다."""
    return re.sub(r"[ \t]+", " ", _INVISIBLE.sub("", unicodedata.normalize("NFKC", text)))


_PHONE = re.compile(r"(?<!\d)(01[016789]|0\d{1,2})[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")
_RRN = re.compile(r"(?<!\d)\d{6}[-\s]?[1-4]\d{6}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_QUOTE_HEADER = re.compile(r"^(On .{5,120} wrote:|-{2,}\s*Original Message\s*-{2,}|.{0,80}님이 작성:|\d{4}년 .{3,60}작성:)\s*$", re.I)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._skip += 1
        if tag in ("br", "p", "div", "li", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    return "".join(p.parts)


def strip_quotes_and_signature(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if _QUOTE_HEADER.match(s) or s == "--" or s == "-- ":
            break
        if s.startswith(">"):
            continue
        out.append(line)
    return "\n".join(out)


def mask_sensitive(text: str) -> str:
    text = _RRN.sub("[RRN]", text)
    text = _CARD.sub(lambda m: "[NUMBER]" if len(re.sub(r"\D", "", m.group())) >= 13 else m.group(), text)
    return _PHONE.sub("[PHONE]", text)


def detect_injection(text: str) -> list[str]:
    t = _norm(text)
    return [name for name, pat in STRONG_PATTERNS if pat.search(t)]


def detect_suspicion(text: str) -> list[str]:
    t = _norm(text)
    return [name for name, pat in WEAK_PATTERNS if pat.search(t)]


def detect_language(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en"
    hangul = sum("가" <= c <= "힣" for c in letters)
    return "ko" if hangul / len(letters) > 0.2 else "en"


def auto_signals(raw: RawMail) -> list[str]:
    h = {k.lower(): v for k, v in raw.headers.items()}
    sig = []
    if "list-unsubscribe" in h:
        sig.append("list-unsubscribe")
    if h.get("precedence", "").lower() in ("bulk", "list", "junk"):
        sig.append("precedence-bulk")
    if h.get("auto-submitted", "no").lower() != "no":
        sig.append("auto-submitted")
    if re.search(r"(no[-_.]?reply|do[-_.]?not[-_.]?reply|mailer-daemon)@", raw.sender, re.I):
        sig.append("noreply-sender")
    return sig


def sanitize(raw: RawMail) -> MailRef:
    text = raw.body_text or html_to_text(raw.body_html)
    # 인젝션은 정제 전 원문 기준으로 탐지 (인용문 속 지시문도 신호로 취급)
    full = f"{raw.subject}\n{text}"
    flags, weak = detect_injection(full), detect_suspicion(full)
    body = mask_sensitive(strip_quotes_and_signature(text)).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)[:MAX_BODY_CHARS]
    return MailRef(
        id=raw.id, thread_id=raw.thread_id, sender=raw.sender, sender_name=raw.sender_name,
        subject=raw.subject, date=raw.date, message_id=raw.message_id_header, body=body, language=detect_language(body or raw.subject),
        auto_signals=auto_signals(raw), injection_flags=flags, suspicion_flags=weak,
    )
