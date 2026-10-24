import { useEffect, useRef, useState } from 'react'
import { Pause, Play, Radio } from 'lucide-react'
import clsx from 'clsx'
import type { LiveEvent } from '@/api/types'
import { Badge, Card, CardHeader, PageHeader } from '@/components/ui'
import { useLiveEvents, type NodeState } from '@/hooks'

interface N { id: string; label: string; x: number; y: number; w: number; sub?: string; kind: 'sup' | 'agent' | 'gate' | 'ext' }
const nodes: N[] = [
  { id: 'supervisor', label: 'Supervisor', sub: 'plan · route · policy', x: 380, y: 36, w: 200, kind: 'sup' },
  { id: 'triage', label: 'Triage', sub: 'Haiku', x: 70, y: 150, w: 124, kind: 'agent' },
  { id: 'context', label: 'Context', sub: 'Haiku', x: 215, y: 150, w: 124, kind: 'agent' },
  { id: 'drafting', label: 'Drafting', sub: 'Sonnet', x: 360, y: 150, w: 124, kind: 'agent' },
  { id: 'reviewer', label: 'Reviewer', sub: 'Sonnet', x: 505, y: 150, w: 124, kind: 'agent' },
  { id: 'delivery', label: 'Delivery', sub: '결정적', x: 650, y: 150, w: 124, kind: 'agent' },
  { id: 'tool_gateway', label: 'Tool Gateway', sub: 'capability 검사', x: 380, y: 270, w: 200, kind: 'gate' },
  { id: 'gmail', label: 'Gmail API', sub: 'read · draft', x: 650, y: 270, w: 124, kind: 'ext' },
]
const H = 28
const stateColor: Record<NodeState, { fill: string; stroke: string }> = {
  idle: { fill: 'var(--surface)', stroke: 'var(--border)' },
  active: { fill: 'var(--accent-soft)', stroke: 'var(--accent)' },
  done: { fill: 'var(--ok-soft)', stroke: 'var(--ok)' },
  retry: { fill: 'var(--warn-soft)', stroke: 'var(--warn)' },
  error: { fill: 'var(--bad-soft)', stroke: 'var(--bad)' },
  waiting: { fill: 'var(--sup-soft)', stroke: 'var(--sup)' },
}
const edges: [string, string][] = [
  ['supervisor', 'triage'], ['supervisor', 'context'], ['supervisor', 'drafting'], ['supervisor', 'reviewer'], ['supervisor', 'delivery'],
  ['context', 'tool_gateway'], ['delivery', 'tool_gateway'], ['tool_gateway', 'gmail'],
]
const dot: Record<string, string> = { supervisor: 'bg-sup', tool_gateway: 'bg-warn' }
const stateText: Record<NodeState, string> = { idle: '대기', active: '실행 중', done: '완료', retry: '재시도 요청', error: '차단', waiting: '사람 대기' }

export default function Live() {
  const live = useLiveEvents()
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]))
  const st = (id: string): NodeState => (id === 'gmail' ? (live.nodes.tool_gateway === 'active' ? 'active' : live.nodes.tool_gateway === 'done' ? 'done' : 'idle') : (live.nodes[id] ?? 'idle'))

  return (
    <>
      <PageHeader title="실시간 에이전트 모니터" desc="Supervisor와 에이전트의 실행 상태를 SSE 스트림으로 실시간 표시합니다. (목업: 시나리오 재생 · 실제: LangGraph 이벤트 중계)"
        right={
          <div className="flex items-center gap-2">
            <Badge tone={live.connected ? 'ok' : 'bad'}><Radio size={12} className={live.connected && !live.paused ? 'animate-pulse' : ''} /> {live.connected ? (live.paused ? 'PAUSED' : 'LIVE') : '연결 끊김'}</Badge>
            <button onClick={live.togglePause} className="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-sm hover:bg-surface2">
              {live.paused ? <><Play size={14} /> 재개</> : <><Pause size={14} /> 일시정지</>}
            </button>
          </div>
        } />

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <div className="flex min-w-0 flex-col gap-4">
          <Card>
            <CardHeader title={live.subject ? `처리 중: ${live.subject}` : '다음 메일 대기 중…'} right={<Elapsed start={live.startedAt} done={live.finished} />} />
            <div className="p-2">
              <svg viewBox="0 0 760 330" className="w-full" role="img" aria-label="에이전트 실행 그래프">
                {edges.map(([a, b]) => {
                  const A = byId[a], B = byId[b]
                  const hot = st(b) === 'active' && (st(a) !== 'idle' || a === 'supervisor')
                  return <line key={a + b} x1={A.x} y1={A.y + H} x2={B.x} y2={B.y - H} stroke={hot ? 'var(--accent)' : 'var(--border)'} strokeWidth={hot ? 2.5 : 1.5} strokeDasharray={hot ? '6 4' : undefined} className={hot ? 'flow' : ''} />
                })}
                {nodes.map((n) => {
                  const s = st(n.id), c = stateColor[s]
                  return (
                    <g key={n.id}>
                      <rect x={n.x - n.w / 2} y={n.y - H} width={n.w} height={H * 2} rx={10} fill={c.fill} stroke={c.stroke} strokeWidth={s === 'idle' ? 1.5 : 2.5} className={s === 'active' ? 'pulse' : ''} />
                      <text x={n.x} y={n.y - 3} textAnchor="middle" fontSize={14} fontWeight={600} fill="var(--text)">{n.label}</text>
                      <text x={n.x} y={n.y + 14} textAnchor="middle" fontSize={11} fill="var(--muted)">{s === 'idle' ? n.sub : stateText[s]}</text>
                    </g>
                  )
                })}
              </svg>
            </div>
          </Card>

          <Card>
            <CardHeader title="초안 스트리밍 (Drafting)" right={live.nodes.drafting === 'active' ? <Badge tone="accent">작성 중</Badge> : undefined} />
            <pre className="min-h-28 whitespace-pre-wrap px-4 py-3 font-sans text-sm leading-relaxed">
              {live.draft || <span className="text-muted">초안 작성 단계에서 토큰이 실시간으로 표시됩니다.</span>}
              {live.nodes.drafting === 'active' && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-accent align-middle" />}
            </pre>
          </Card>
        </div>

        <EventLog events={live.events} />
      </div>
      <style>{`
        @keyframes dash { to { stroke-dashoffset: -20 } } .flow { animation: dash .6s linear infinite }
        @keyframes pulse { 50% { opacity: .55 } } .pulse { animation: pulse 1.1s ease-in-out infinite }
      `}</style>
    </>
  )
}

function Elapsed({ start, done }: { start?: number; done: boolean }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { if (done) return; const t = setInterval(() => setNow(Date.now()), 100); return () => clearInterval(t) }, [done])
  if (!start) return null
  return <span className="font-mono text-xs tabular-nums text-muted">{((now - start) / 1000).toFixed(1)}s{done && ' · 완료'}</span>
}

function EventLog({ events }: { events: LiveEvent[] }) {
  const ref = useRef<HTMLUListElement>(null)
  const shown = events.filter((e) => e.type !== 'token')
  useEffect(() => { const el = ref.current; if (el) el.scrollTop = el.scrollHeight }, [shown.length])
  return (
    <Card className="flex min-h-0 flex-col xl:max-h-[calc(100vh-190px)]">
      <CardHeader title="이벤트 로그" right={<span className="text-xs text-muted">{shown.length}건</span>} />
      <ul ref={ref} className="min-h-72 flex-1 divide-y divide-line overflow-y-auto">
        {shown.length === 0 && <li className="p-6 text-center text-sm text-muted">이벤트 대기 중…</li>}
        {shown.map((e) => (
          <li key={e.seq} className="flex gap-3 px-4 py-2 text-sm">
            <span className="mt-1.5 shrink-0"><span className={clsx('block h-2 w-2 rounded-full', dot[e.actor] ?? 'bg-accent')} /></span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs">{e.actor}</span>
                <span className="text-xs text-muted">{e.type}</span>
                {e.status === 'retry' && <Badge tone="warn">재작성</Badge>}
                {e.status === 'error' && <Badge tone="bad">차단</Badge>}
                {e.status === 'waiting' && <Badge tone="sup">대기</Badge>}
              </div>
              <div className={clsx(e.status === 'error' && 'text-bad')}>{e.message}</div>
              {(e.model || e.tokens) && <div className="font-mono text-xs text-muted">{e.model} {e.tokens ? `· ${e.tokens.toLocaleString()} tok` : ''}</div>}
            </div>
            <time className="shrink-0 font-mono text-xs text-muted">{new Date(e.ts).toLocaleTimeString('en-GB')}</time>
          </li>
        ))}
      </ul>
    </Card>
  )
}
