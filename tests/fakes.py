from mail_agent.schemas import Classification, ContextPack, DraftResult, RawMail, Review


class FakeLLM:
    """with_structured_output(Schema).invoke(msgs) -> handlers[Schema.__name__](msgs). 호출 기록을 남긴다."""

    def __init__(self, **handlers):
        self.handlers, self.calls = handlers, []

    def __call__(self, tier: str):
        outer = self

        class _Model:
            def with_structured_output(self, schema):
                class _Chain:
                    def invoke(_s, msgs):
                        outer.calls.append((schema.__name__, msgs))
                        h = outer.handlers.get(schema.__name__)
                        if h is None:
                            raise AssertionError(f"예상치 못한 LLM 호출: {schema.__name__}")
                        return h(msgs)
                return _Chain()
        return _Model()

    def count(self, name: str) -> int:
        return sum(1 for n, _ in self.calls if n == name)


def mail(id="m1", thread="t1", sender="kim@acme.example", subject="견적 회신 요청", body="금요일까지 수정 견적서 회신 부탁드립니다.", headers=None, **kw):
    return RawMail(id=id, thread_id=thread, sender=sender, sender_name="김서연", subject=subject, date="Fri, 24 Oct 2026",
                   body_text=body, headers=headers or {}, message_id_header=f"<{id}@x>", **kw)


def happy_llm(**over):
    h = dict(
        Classification=lambda m: Classification(label="reply_needed", confidence=0.95, reason="직접 요청"),
        ContextPack=lambda m: ContextPack(summary="이전 논의 요약"),
        DraftResult=lambda m: DraftResult(body="안녕하세요. 금요일까지 회신드리겠습니다. 감사합니다."),
        Review=lambda m: Review(passed=True, issues=[]),
    )
    h.update(over)
    return FakeLLM(**h)
