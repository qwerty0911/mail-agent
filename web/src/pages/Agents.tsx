import { useQuery } from '@tanstack/react-query'
import { Lock } from 'lucide-react'
import { api } from '@/api/client'
import type { AgentManifest } from '@/api/types'
import { Badge, Card, PageHeader, riskMeta } from '@/components/ui'

export default function Agents() {
  const { data = [] } = useQuery({ queryKey: ['agents'], queryFn: api.agents })
  const active = data.filter((a) => !a.planned)
  const planned = data.filter((a) => a.planned)
  return (
    <>
      <PageHeader title="에이전트 레지스트리" desc="Manifest(agents/<name>/manifest.yaml)로 등록된 에이전트입니다. 도구 권한(capability)은 Tool Gateway가 호출자별로 검사합니다." />
      <div className="grid gap-4 xl:grid-cols-2">{active.map((a) => <AgentCard key={a.name} a={a} />)}</div>
      <h2 className="mb-3 mt-8 text-sm font-semibold text-muted">확장 후보 (미구현 · 온보딩 게이트 대기)</h2>
      <div className="grid gap-4 xl:grid-cols-3">{planned.map((a) => <AgentCard key={a.name} a={a} />)}</div>
    </>
  )
}

function AgentCard({ a }: { a: AgentManifest }) {
  return (
    <Card className={a.planned ? 'border-dashed opacity-80' : ''}>
      <div className="flex items-start justify-between gap-2 px-4 pt-4">
        <div>
          <div className="font-mono text-sm font-semibold">{a.name}</div>
          <div className="text-xs text-muted">team: {a.team}</div>
        </div>
        <div className="flex gap-1.5">
          <Badge tone={riskMeta[a.riskTier].tone}>risk {riskMeta[a.riskTier].text}</Badge>
          <Badge tone="sup">{a.modelTier === 'none' ? 'LLM 없음' : a.modelTier}</Badge>
        </div>
      </div>
      <p className="px-4 pt-2 text-sm">{a.description}</p>
      <dl className="grid grid-cols-[96px_1fr] gap-y-1.5 px-4 py-3 text-xs">
        <dt className="text-muted">입출력</dt><dd className="font-mono">{a.inputSchema} → {a.outputSchema}</dd>
        <dt className="text-muted">capabilities</dt>
        <dd className="flex flex-wrap gap-1">
          {a.capabilities.length ? a.capabilities.map((c) => <Badge key={c} tone="warn"><Lock size={10} />{c}</Badge>) : <span className="text-muted">없음 (도구 호출 불가)</span>}
        </dd>
        <dt className="text-muted">한도</dt><dd>{a.limits.maxSteps}스텝 · {a.limits.maxTokens} tok · {a.limits.timeoutS}s</dd>
        <dt className="text-muted">평가</dt>
        <dd className="flex flex-wrap items-center gap-1"><span className="font-mono">{a.evalDataset}</span>{a.evaluators.map((e) => <Badge key={e}>{e}</Badge>)}</dd>
      </dl>
    </Card>
  )
}
