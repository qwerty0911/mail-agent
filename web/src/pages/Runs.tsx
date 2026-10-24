import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { api } from '@/api/client'
import type { TraceStep } from '@/api/types'
import { Badge, Card, CardHeader, PageHeader, Stat } from '@/components/ui'

const actorTone: Record<string, string> = {
  supervisor: 'bg-sup', tool_gateway: 'bg-warn', triage: 'bg-accent', context: 'bg-accent',
  drafting: 'bg-accent', reviewer: 'bg-accent', delivery: 'bg-accent',
}
const statusTone = { ok: 'ok', retry: 'warn', error: 'bad', waiting: 'neutral' } as const

export default function Runs() {
  const { runId = 'r2' } = useParams()
  const nav = useNavigate()
  const { data: mails = [] } = useQuery({ queryKey: ['mails'], queryFn: api.mails })
  const { data: run } = useQuery({ queryKey: ['run', runId], queryFn: () => api.run(runId) })
  const total = run?.durationMs ?? 1

  return (
    <>
      <PageHeader title="실행 트레이스" desc="Supervisor 결정과 에이전트·도구 호출을 시간순으로 보여줍니다. 실제 환경에서는 LangSmith trace와 1:1로 연결됩니다."
        right={
          <select value={runId} onChange={(e) => nav(`/runs/${e.target.value}`)} className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm">
            {mails.map((m) => <option key={m.runId} value={m.runId}>{m.runId} · {m.subject.slice(0, 28)}</option>)}
          </select>
        } />
      {run && (
        <>
          <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="총 소요" value={`${(run.durationMs / 1000).toFixed(1)}s`} />
            <Stat label="비용" value={run.costUsd > 0 ? `$${run.costUsd.toFixed(4)}` : '—'} sub={run.costUsd > 0 ? undefined : 'LangSmith에서 확인'} />
            <Stat label="스텝" value={run.steps.length} />
            <Stat label="토큰" value={run.steps.reduce((a, s) => a + (s.tokens ?? 0), 0).toLocaleString()} />
          </div>
          <Card>
            <CardHeader title="타임라인" right={<Link to="/" className="text-xs text-accent hover:underline">← 검토 큐</Link>} />
            <ul className="divide-y divide-line">
              {run.steps.map((s) => <Row key={s.id} s={s} total={total} />)}
            </ul>
          </Card>
        </>
      )}
    </>
  )
}

function Row({ s, total }: { s: TraceStep; total: number }) {
  return (
    <li className="grid gap-x-4 gap-y-1 px-4 py-3 md:grid-cols-[170px_1fr_280px]">
      <div className="flex items-center gap-2">
        <span className={clsx('h-2.5 w-2.5 rounded-full', actorTone[s.actor] ?? 'bg-muted')} />
        <span className="font-mono text-xs">{s.actor}</span>
        <Badge tone={statusTone[s.status]}>{s.kind}</Badge>
      </div>
      <div className="min-w-0">
        <div className="text-sm">{s.title}</div>
        {s.detail && <div className="mt-0.5 text-xs text-muted">{s.detail}</div>}
        {s.model && <div className="mt-0.5 font-mono text-xs text-muted">{s.model}{s.tokens ? ` · ${s.tokens.toLocaleString()} tok` : ''}</div>}
      </div>
      <div className="flex items-center gap-2">
        <div className="relative h-2 flex-1 rounded-full bg-surface2">
          <div className={clsx('absolute h-2 rounded-full', actorTone[s.actor] ?? 'bg-muted')}
            style={{ left: `${(s.startMs / total) * 100}%`, width: `${Math.max((s.durMs / total) * 100, 1)}%` }} />
        </div>
        <span className="w-14 text-right font-mono text-xs tabular-nums text-muted">{s.durMs}ms</span>
      </div>
    </li>
  )
}
