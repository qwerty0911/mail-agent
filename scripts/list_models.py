"""계정에서 실제 호출 가능한 모델 ID 조회 (OpenAI). 사용: list_models.py [검색어]"""
import sys

from openai import OpenAI

from mail_agent.settings import ROOT
from dotenv import dotenv_values

key = dotenv_values(ROOT / ".env").get("OPENAI_API_KEY")
if not key:
    sys.exit("✗ .env 에 OPENAI_API_KEY 가 없음")
q = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
ids = sorted(m.id for m in OpenAI(api_key=key).models.list() if q in m.id.lower())
print("\n".join(ids) or "(일치하는 모델 없음)")
