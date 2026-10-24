import { useQuery } from '@tanstack/react-query'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '@/api/client'
import type { EvalLayer, Experiment } from '@/api/types'
import { Badge, Card, CardHeader, PageHeader } from '@/components/ui'

const layers: { key: EvalLayer; title: string; desc: string }[] = [
  { key: 'unit', title: 'Unit · 에이전트별', desc: '에이전트 단독 품질' },
  { key: 'orchestration', title: 'Orchestration · Supervisor', desc: '라우팅·trajectory·예산' },
  { key: 'e2e', title: 'End-to-end', desc: '합성 메일함 전체 시나리오' },
]

const failing = (x: Experiment) => Object.entries(x.thresholds).filter(([k, t]) => (x.metrics[k] ?? 0) < t).map(([k]) => k)
const pct = (k: string, v: number) => (k.includes('latency') ? `${v}s` : k.includes('usd') ? `$${v}` : `${(v * 100).toFixed(0)}%`)

export default function Evals() {
  const { data = [] } = useQuery({ queryKey: ['exps'], queryFn: api.experiments })
  const triage = data.filter((x) => x.target === 'triage').map((x) => ({ name: x.name.replace('triage-', ''), recall: x.metrics.recall * 100, precision: x.metrics.precision * 100 }))

  return (
    <>
      <PageHeader title="평가 (LangSmith)" desc="3계층 평가 결과입니다. 임계값 미달 실험은 빨간색으로 표시되고, 원인 에이전트를 trace로 추적합니다." />
      <Card className="mb-6">
        <CardHeader title="Triage Recall / Precision 추이" right={<Badge tone="bad">회귀 탐지: triage-relaxed-criteria</Badge>} />
        <div className="h-64 px-2 py-3">
          <ResponsiveContainer>
            <LineChart data={triage} margin={{ left: 0, right: 16 }}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
              <XAxis dataKey="name" stroke="var(--muted)" fontSize={12} />
              <YAxis domain={[70, 100]} ticks={[70, 80, 90, 100]} stroke="var(--muted)" fontSize={12} unit="%" />
              <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }} />
              <ReferenceLine y={95} stroke="var(--bad)" strokeDasharray="4 4" label={{ value: 'Recall 목표 95%', fill: 'var(--bad)', fontSize: 11, position: 'insideBottomRight' }} />
              <Line dataKey="recall" name="Recall" stroke="var(--accent)" strokeWidth={2} dot />
              <Line dataKey="precision" name="Precision" stroke="var(--sup)" strokeWidth={2} dot strokeDasharray="5 3" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {layers.map((l) => (
        <Card key={l.key} className="mb-4 overflow-x-auto">
          <CardHeader title={l.title} right={<span className="text-xs text-muted">{l.desc}</span>} />
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr><th className="px-4 py-2 font-medium">실험</th><th className="px-2 font-medium">대상</th><th className="px-2 font-medium">지표</th><th className="px-4 font-medium">결과</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.filter((x) => x.layer === l.key).map((x) => {
                const f = failing(x)
                return (
                  <tr key={x.id} className={f.length ? 'bg-badsoft/50' : ''}>
                    <td className="px-4 py-2.5"><div className="font-mono text-xs">{x.name}</div>{x.note && <div className="text-xs text-muted">{x.note}</div>}</td>
                    <td className="px-2"><Badge>{x.target}</Badge></td>
                    <td className="px-2">
                      <div className="flex flex-wrap gap-x-4 gap-y-1">
                        {Object.entries(x.metrics).map(([k, v]) => (
                          <span key={k} className={f.includes(k) ? 'text-bad' : ''}><span className="text-xs text-muted">{k} </span><span className="tabular-nums">{pct(k, v)}</span></span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4">{f.length ? <Badge tone="bad">FAIL · {f.join(', ')}</Badge> : <Badge tone="ok">PASS</Badge>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>
      ))}
    </>
  )
}
