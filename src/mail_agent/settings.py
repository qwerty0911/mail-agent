from pathlib import Path

from dotenv import load_dotenv
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

# 요청 가능한 Gmail 스코프는 이 두 개뿐. gmail.send / gmail.modify 는 코드 어디에서도 요청하지 않는다.
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # 모델은 "provider:model_id" 형식 (예: openai:xxx, anthropic:xxx). 제공자 교체는 .env 만 수정.
    model_light: str
    model_standard: str
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    langsmith_api_key: SecretStr
    langsmith_project: str = "mail-agent-dev"

    gmail_client_secret_file: Path = ROOT / ".secrets/gmail_client_secret.json"
    gmail_token_file: Path = ROOT / ".secrets/gmail_token.json"
    gmail_target_label: str = "mail-agent"

    data_dir: Path = ROOT / "data"
    api_token: SecretStr | None = None       # 대시보드 API 인증 토큰 (X-API-Key)


def get_settings() -> Settings:
    # LangSmith(LANGSMITH_*) 등 SDK 가 os.environ 에서 읽는 값을 위해 .env 도 환경에 반영
    load_dotenv(ROOT / ".env", override=False)
    return Settings()  # type: ignore[call-arg]
