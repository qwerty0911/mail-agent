"""LLM 생성 단일 관문. 에이전트 코드는 티어(light/standard)만 알고 제공자·모델명은 모른다."""
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from mail_agent.settings import get_settings

Tier = Literal["light", "standard"]


def make_chat_model(tier: Tier, **kwargs) -> BaseChatModel:
    s = get_settings()
    spec = s.model_light if tier == "light" else s.model_standard
    provider, _, name = spec.partition(":")
    if not name:
        raise ValueError(f"모델 지정은 'provider:model_id' 형식이어야 함: {spec!r}")
    keys = {"openai": s.openai_api_key, "anthropic": s.anthropic_api_key}
    key = keys.get(provider)
    if key is None:
        raise ValueError(f"{provider} API 키가 .env 에 없음")
    return init_chat_model(name, model_provider=provider, api_key=key.get_secret_value(), **kwargs)
