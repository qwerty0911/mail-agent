"""에이전트 간 통신 계약. 에이전트는 자유 텍스트가 아니라 이 스키마로만 데이터를 주고받는다."""
from typing import Literal

from pydantic import BaseModel, Field

Label = Literal["reply_needed", "fyi", "newsletter", "spam", "auto"]


class MailRef(BaseModel):
    """sanitize 를 거친 메일. body 는 비신뢰 데이터(untrusted)이며 LLM 프롬프트에서 '데이터'로만 취급한다."""
    id: str
    thread_id: str
    sender: str
    sender_name: str = ""
    subject: str
    date: str = ""
    message_id: str = ""
    body: str
    language: Literal["ko", "en"] = "en"
    auto_signals: list[str] = Field(default_factory=list)       # List-Unsubscribe, noreply 등
    injection_flags: list[str] = Field(default_factory=list)   # 강한 신호 → 차단
    suspicion_flags: list[str] = Field(default_factory=list)   # 약한 신호 → 표시·추가 점검
    untrusted: bool = True


class Classification(BaseModel):
    label: Label
    confidence: float
    reason: str


class ContextPack(BaseModel):
    prior_messages: int = 0
    summary: str = ""


class DraftResult(BaseModel):
    body: str


class Review(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)


class DeliveryReceipt(BaseModel):
    draft_id: str
    notified: bool = False


class ClassDecision(BaseModel):
    """저신뢰 분류에 대한 사람의 결정."""
    reply_needed: bool


# artifact 이름 → 검증 스키마 (Supervisor 가 에이전트 산출물을 이 계약으로 검증)
ARTIFACT_SCHEMAS: dict[str, type[BaseModel]] = {
    "mail": MailRef,
    "classification": Classification,
    "context": ContextPack,
    "draft": DraftResult,
    "review": Review,
    "receipt": DeliveryReceipt,
    "class_decision": ClassDecision,
}


class RawMail(BaseModel):
    """메일함에서 읽은 원본(미정제). 이 객체는 Supervisor/LLM 에 전달되지 않는다."""
    id: str
    thread_id: str
    sender: str
    sender_name: str = ""
    to: str = ""
    subject: str = ""
    date: str = ""
    body_text: str = ""
    body_html: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    message_id_header: str = ""
