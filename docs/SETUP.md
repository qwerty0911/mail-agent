# 3단계 — Tool 셋업·연동 가이드

> **보안 원칙**: API 키·OAuth 파일·봇 토큰은 **채팅/이슈/커밋에 절대 붙여넣지 않는다.** 아래 지정된 파일에 직접 저장하고, 점검 스크립트(`scripts/check_setup.py`)는 값을 출력하지 않는다.

## 진행 현황
| 항목 | 담당 | 상태 |
|---|---|---|
| Python 프로젝트·의존성(uv), `.gitignore`, `.env.example`, 설정 모듈 | Claude | ✅ 완료 |
| `scripts/gmail_auth.py` (스코프 검증 포함), `scripts/check_setup.py` | Claude | ✅ 완료 |
| Hermes MCP 설정 템플릿 `hermes/config.mcp.example.yaml` | Claude | ✅ 완료 |
| Anthropic / LangSmith 키 발급·`.env` 입력 | **사용자** | ⬜ §1~2 |
| Google Cloud OAuth 클라이언트 생성·동의 | **사용자** | ⬜ §3 |
| Hermes v0.22.5 설치 (스크립트 검토 후 실행, sha256 `abf33860…`) | Claude | ✅ 완료 (`~/.hermes`, PATH는 `~/.local/bin`) |
| Hermes 모델 설정·Telegram 봇·허용 사용자 ID | **사용자** | ⬜ §4-2~4 |

## 1. `.env` 만들기
```bash
cp .env.example .env && chmod 600 .env
```
`ANTHROPIC_API_KEY` 입력 (console.anthropic.com → API Keys). 이 프로젝트 전용 키를 새로 만들고 월 사용 한도를 설정할 것.

## 2. LangSmith
smith.langchain.com → Settings → API Keys → 새 키 생성 → `.env`의 `LANGSMITH_API_KEY`.
- `LANGSMITH_HIDE_INPUTS/OUTPUTS=true` 가 기본. **실제 메일 처리 시 원문이 LangSmith로 전송되지 않는다.** 합성 데이터로 평가·시연할 때만 `false`.
- 프로젝트명 `mail-agent-dev` (자동 생성됨).

## 3. Gmail OAuth (최소 권한)
1. console.cloud.google.com → 새 프로젝트 `mail-agent`
2. **APIs & Services → Library → Gmail API → Enable**
3. **OAuth 동의 화면(Google Auth Platform)**: 사용자 유형 *External*(Workspace 계정이면 *Internal* 권장), 게시 상태 *Testing*, **테스트 사용자에 본인 계정 추가**
4. **Data Access(범위)** 에 아래 **2개만** 추가
   - `.../auth/gmail.readonly`
   - `.../auth/gmail.compose`  ← 초안 생성용 (`gmail.send` 는 추가하지 말 것)
5. **Credentials → Create Credentials → OAuth client ID → Desktop app** → JSON 다운로드 → 아래 경로로 이동
   ```bash
   mv ~/Downloads/client_secret_*.json .secrets/gmail_client_secret.json && chmod 600 .secrets/gmail_client_secret.json
   ```
6. Gmail에서 라벨 `mail-agent` 생성 (처음엔 이 라벨 붙인 메일만 처리 → 영향 범위 최소화)
7. 인증 실행 (브라우저 동의 창이 열림)
   ```bash
   uv run python scripts/gmail_auth.py
   ```
   부여 스코프가 위 2개보다 넓으면 토큰을 저장하지 않고 중단한다.

> ⚠ *Testing* 상태에서는 refresh token이 **7일마다 만료**된다. 개발 중에는 `gmail_auth.py` 재실행으로 충분하며, 상시 운영 시점에 별도 결정(게시 전환/Workspace Internal).
> `gmail.compose` 는 사실상 *초안 생성·발송 가능* 스코프다. 발송 방지는 **코드에 send 호출이 없고 Tool Gateway가 `drafts.create`만 허용**하는 구조(PRD §6)로 보장하며, 4단계에서 이를 테스트로 고정한다.

## 4. Hermes Gateway
공식 문서: [Quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart) · [Telegram](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram) · [MCP](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)

1. **설치** — ✅ 완료. (참고용 절차) (macOS): 공식 설치 스크립트를 내려받아 *내용 확인 후* 실행
   ```bash
   curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o /tmp/hermes-install.sh && less /tmp/hermes-install.sh
   bash /tmp/hermes-install.sh && source ~/.zshrc
   ```
2. **Hermes 자체 LLM 설정**: `hermes model` (Hermes 대화용. 우리 에이전트의 LLM과 별개이며 키는 `~/.hermes/.env` 에 저장됨)
3. **메신저 봇 + 허용 사용자(필수)**
   - Telegram: @BotFather → `/newbot` → 토큰 / @userinfobot 으로 **숫자 user ID** 확인
   - `hermes gateway setup` → Telegram 선택 → 토큰·허용 user ID 입력
   - 수동: `~/.hermes/.env` 에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS` (**비우면 전원 차단이 기본이며, `GATEWAY_ALLOW_ALL_USERS` 는 사용 금지**)
   - Slack 선택 시: Socket Mode 의 `xapp-` / `xoxb-` 토큰, `SLACK_ALLOWED_USERS`
4. **동작 확인**: `hermes gateway` 실행 → 봇에게 메시지 → 응답 확인
5. **MCP 연결**: 4단계에서 MCP 서버 구현 후 `hermes/config.mcp.example.yaml` 내용을 `~/.hermes/config.yaml` 에 병합 (진입점 도구 4개만 `tools.include`)

## 5. 점검
```bash
uv run python scripts/check_setup.py
```
기대 결과: `.env 로드` · `파일 권한` · `Anthropic` · `LangSmith` · `Gmail 토큰·스코프` · `Hermes CLI` 모두 ✓.

## 6. 보안 체크리스트
- [ ] `.env`, `.secrets/*` 권한 600/700, git 제외 확인 (`git init` 시 `git status` 로 미추적 확인)
- [ ] Anthropic 전용 키 + 월 한도
- [ ] OAuth 스코프 2개만, 테스트 사용자 = 본인만
- [ ] Hermes 허용 사용자 ID 지정, allow-all 미사용
- [ ] LangSmith HIDE_INPUTS/OUTPUTS=true (실메일 처리 시)
- [ ] 키가 노출됐다고 의심되면 즉시 폐기·재발급
