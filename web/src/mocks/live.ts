import type { LiveEvent, LiveEventType } from '@/api/types'

type Step = [delayMs: number, type: LiveEventType, actor: string, message: string, extra?: Partial<LiveEvent>]

const draftV1 = "Hi Daniel,\n\nThanks for the heads-up. I can confirm Nov 4 works on our side and we'll start onboarding then.\n\nBest regards,"
const draftV2 = "Hi Daniel,\n\nThanks for the heads-up. I'll check the team's availability for Nov 4 and confirm by end of day tomorrow.\n\nBest regards,"

const stream = (actor: string, text: string, chunk = 4): Step[] =>
  (text.match(new RegExp(`[\\s\\S]{1,${chunk}}`, 'g')) ?? []).map((d) => [45, 'token', actor, '', { delta: d }] as Step)

export const script = (subject: string): Step[] => [
  [600, 'run_started', 'supervisor', '새 메일 처리 시작', { subject }],
  [300, 'node_started', 'supervisor', 'intake · sanitize (HTML 제거, PII 마스킹)'],
  [700, 'node_finished', 'supervisor', 'sanitize 완료 · 인젝션 패턴 없음', { status: 'ok' }],
  [200, 'node_started', 'triage', 'classify', { model: 'claude-haiku-5-5' }],
  [900, 'node_finished', 'triage', 'label=reply_needed · confidence=0.94', { status: 'ok', tokens: 640 }],
  [150, 'policy', 'supervisor', 'policy check · 예산 3/8 스텝, 허용'],
  [200, 'node_started', 'context', '스레드·발신자 이력 수집', { model: 'claude-haiku-5-5' }],
  [250, 'tool_call', 'tool_gateway', 'gmail.threads.get · caller=context · capability=gmail.read ✓'],
  [800, 'node_finished', 'context', 'ContextPack 생성 (이전 교신 2건)', { status: 'ok', tokens: 1480 }],
  [200, 'node_started', 'drafting', '초안 작성 v1', { model: 'claude-sonnet-5-5' }],
  ...stream('drafting', draftV1),
  [200, 'node_finished', 'drafting', '초안 v1 완성', { status: 'ok', tokens: 2310 }],
  [200, 'node_started', 'reviewer', '검수', { model: 'claude-sonnet-5-5' }],
  [1300, 'node_finished', 'reviewer', '실패: 확정되지 않은 날짜를 약속함 → 재작성 요청', { status: 'retry', tokens: 1750 }],
  [250, 'policy', 'supervisor', '재시도 1/1 허용 · drafting 재투입'],
  [200, 'node_started', 'drafting', '초안 작성 v2 (검수 지적 반영)', { model: 'claude-sonnet-5-5' }],
  ...stream('drafting', draftV2),
  [200, 'node_finished', 'drafting', '초안 v2 완성', { status: 'ok', tokens: 2100 }],
  [200, 'node_started', 'reviewer', '재검수', { model: 'claude-sonnet-5-5' }],
  [1000, 'node_finished', 'reviewer', '통과', { status: 'ok', tokens: 1600 }],
  [200, 'node_started', 'delivery', 'Gmail 초안 저장'],
  [250, 'tool_call', 'tool_gateway', 'gmail.drafts.create · caller=delivery · capability=gmail.draft.create ✓'],
  [500, 'node_finished', 'delivery', 'draft_id=d2 저장 완료', { status: 'ok' }],
  [300, 'hitl_wait', 'supervisor', '사용자 승인 대기 (Hermes → Telegram)', { status: 'waiting' }],
  [2500, 'run_finished', 'supervisor', '사용자 승인 · 완료 (13.4s, $0.0214)', { status: 'ok' }],
]

export function makeEvent(seq: number, runId: string, s: Step): LiveEvent {
  const [, type, actor, message, extra] = s
  return { seq, ts: new Date().toISOString(), runId, type, actor, message, ...extra }
}
