// 백엔드 Pydantic 스키마와 1:1 대응 (추후 OpenAPI → openapi-typescript로 자동 생성으로 대체)
export type Label = 'reply_needed' | 'fyi' | 'newsletter' | 'spam' | 'auto'
export type MailStatus = 'pending_approval' | 'needs_human' | 'approved' | 'discarded' | 'skipped'
export type RiskTier = 'low' | 'medium' | 'high'
export type ModelTier = 'none' | 'light' | 'standard' | 'strong'

export interface Review { passed: boolean; issues: string[] }
export interface Draft { id: string; version: number; body: string; review: Review }

export interface Mail {
  id: string
  runId: string
  threadId: string
  from: { name: string; email: string }
  subject: string
  receivedAt: string
  language: 'ko' | 'en'
  body: string
  label: Label
  confidence: number
  reason: string
  status: MailStatus
  injectionFlagged: boolean
  draft?: Draft
}

export type StepKind = 'plan' | 'route' | 'agent' | 'tool' | 'policy' | 'hitl'
export interface TraceStep {
  id: string
  actor: string // 'supervisor' | agent name | 'tool_gateway'
  kind: StepKind
  title: string
  startMs: number
  durMs: number
  status: 'ok' | 'retry' | 'error' | 'waiting'
  model?: string
  tokens?: number
  detail?: string
}
export interface Run {
  id: string
  mailId: string
  startedAt: string
  durationMs: number
  costUsd: number
  steps: TraceStep[]
}

export interface AgentManifest {
  name: string
  team: string
  description: string
  inputSchema: string
  outputSchema: string
  modelTier: ModelTier
  capabilities: string[]
  riskTier: RiskTier
  limits: { maxSteps: number; maxTokens: number; timeoutS: number }
  evalDataset: string
  evaluators: string[]
  enabled: boolean
  planned?: boolean // 미래 확장 후보
}

export type EvalLayer = 'unit' | 'orchestration' | 'e2e'
export interface Experiment {
  id: string
  name: string
  createdAt: string
  layer: EvalLayer
  target: string
  note?: string
  metrics: Record<string, number>
  thresholds: Record<string, number>
}
export interface ReplyAction {
  type: 'approve' | 'discard' | 'revise' | 'classify'
  instruction?: string
  reply_needed?: boolean // classify: 저신뢰 분류에 대한 사용자 결정
}

// 실시간 이벤트 (백엔드: LangGraph astream_events/stream_mode="custom" → SSE `/api/events`)
export type LiveEventType =
  | 'run_started' | 'node_started' | 'node_finished' | 'token'
  | 'tool_call' | 'policy' | 'hitl_wait' | 'run_finished'
export interface LiveEvent {
  seq: number
  ts: string
  runId: string
  type: LiveEventType
  actor: string // supervisor | triage | context | drafting | reviewer | delivery | tool_gateway
  message: string
  status?: 'ok' | 'retry' | 'error' | 'waiting'
  model?: string
  tokens?: number
  delta?: string // token 이벤트: 스트리밍 조각
  subject?: string // run_started
}
