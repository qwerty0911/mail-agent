# 실행·운영 가이드 (4단계 구축 결과)

## 구조
`src/mail_agent/` — `supervisor/`(계획·정책·HITL) · `agents/<name>/`(manifest.yaml + agent.py) · `registry/` · `gateway/`(capability 검사) ·
`security/sanitize.py` · `tools/mailbox.py`(Gmail/Fake, **send 없음**) · `service.py`(유스케이스) · `api/`(웹, SSE) · `mcp_server/`(Hermes) · `store.py`(SQLite)

## 실행
```bash
uv run pytest -q                                          # 테스트 50개 (LLM·Gmail 미사용)
PYTHONPATH=. uv run python scripts/smoke_run.py           # 합성 메일 + 실제 LLM (Gmail 미접속)
DEMO=1 PYTHONPATH=. uv run python -m mail_agent.api.app   # 데모 API (합성 메일, Gmail 미접속), 127.0.0.1:8000
cd web && npm run dev:real                                # 웹 → 실제 API (프록시가 API_TOKEN 을 헤더로 주입)
cd web && npm run dev                                     # 웹 → MSW 목업
PYTHONPATH=. uv run python -m evals.triage_eval           # LangSmith 평가 (baseline)
```
실메일 모드: `DEMO` 없이 API 실행 → `.env`의 `GMAIL_TARGET_LABEL`(기본 `mail-agent`) 라벨이 붙은 메일만 처리.
처리 이력은 `data/*.sqlite`(gitignore)에 저장되어 재시작 후에도 이어짐.

## 새 에이전트 추가
1. `agents/<name>/manifest.yaml` (requires/produces/when/capabilities/eval) 2. `agent.py` 에 `AGENT_CLASS` 3. 새 artifact 면 `schemas.ARTIFACT_SCHEMAS` 등록
4. 도구 권한이 필요하면 capability 를 Manifest 에 선언 (Gateway 에 등록된 것만 가능) 5. 평가 데이터셋·evaluator 추가. Supervisor 수정 없음 (`tests/test_supervisor.py::test_extensibility…`).

## 보안 보장 (테스트로 고정)
발송 도구/메서드 부재 · Gmail 스코프 2개 · capability 위반 거부+감사 · Supervisor 무도구 · 인젝션 메일은 LLM 호출 전 차단 ·
오염된 이전 스레드 메시지 제외 · 이벤트에 메일 본문 미포함 · API 토큰 없으면 기동 거부.

## 5단계 검증 결과 (합성 35건 + 실제 LLM, Gmail 미접속)
| 항목 | 결과 |
|---|---|
| 회신판단 정확도 / reply_needed Recall / Precision | 33/35 → 데이터셋 정정 후 s21 1건만 오탐 (Recall 100%, Precision ≈95%) |
| 초안: 언어 일치 · 최종 검수 통과 | 18/18 · 18/18 (1차 통과 17/18, s29 는 재작성 루프로 교정) |
| 은밀한 인젝션 3건(카나리·수신자 변경 유도) | 유출 0건 |
| 권한 거부 도구 호출 (정상 흐름) | 0건 |
| LangSmith 트레이스 원문 노출 (100 run 검사) | 0건 |
| 지연 | 평균 4.4s/건, 최대 18s (목표 p95 ≤ 25s) |
| 단위·통합·적대적 테스트 | 50개 통과 |

발견·수정: 인젝션 탐지 약점 7곳(전각·zero-width·간접 지시·ko 변형·수신자 변경·base64 유도·정상 업무메일 오탐) → 정규화 + 강/약 신호 분리.
알려진 잔여 위험: 약한 신호만 있는 외부 전달 요청은 차단하지 않고 Reviewer 에 경고만 전달(LLM 은 도구가 없고 초안은 사람이 승인). 에이전트 timeout_s 는 선언만 됨(미강제).
미수행(승인 필요): 실제 Gmail E2E, Hermes→MCP 연결, Telegram 승인 루프.
