import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, Pencil, ShieldAlert, Trash2 } from 'lucide-react'
import clsx from 'clsx'
import { api } from '@/api/client'
import type { Mail, ReplyAction } from '@/api/types'
import { Badge, Button, Card, CardHeader, PageHeader, Stat, fmtTime, labelMeta, statusMeta } from '@/components/ui'

export default function ReviewQueue() {
  const qc = useQueryClient()
  const { data: mails = [] } = useQuery({ queryKey: ['mails'], queryFn: api.mails })
  const [selId, setSel] = useState<string>('')
  const sel = mails.some((m) => m.id === selId) ? selId : (mails[0]?.id ?? '')
  const [filter, setFilter] = useState<'all' | 'action'>('all')
  const current = mails.find((m) => m.id === sel)

  const act = useMutation({
    mutationFn: (v: { id: string; a: ReplyAction }) => api.act(v.id, v.a),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mails'] }),
  })

  const list = filter === 'action' ? mails.filter((m) => m.status === 'pending_approval' || m.status === 'needs_human') : mails
  const count = (s: Mail['status']) => mails.filter((m) => m.status === s).length

  return (
    <>
      <PageHeader title="검토 큐" desc="Supervisor가 분류·초안 작성·검수를 마친 메일입니다. 승인해도 발송되지 않고 Gmail 초안함에 남습니다." />
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="승인 대기" value={count('pending_approval')} />
        <Stat label="사람 확인 필요" value={count('needs_human')} sub="신뢰도 < 0.6" />
        <Stat label="오늘 승인" value={count('approved')} />
        <Stat label="인젝션 차단" value={mails.filter((m) => m.injectionFlagged).length} sub="초안 생성 차단됨" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <Card className="overflow-hidden">
          <CardHeader title="수신 메일" right={
            <div className="flex gap-1">
              {(['all', 'action'] as const).map((f) => (
                <button key={f} onClick={() => setFilter(f)} className={clsx('cursor-pointer rounded-md px-2 py-1 text-xs', filter === f ? 'bg-accentsoft text-accent' : 'text-muted hover:bg-surface2')}>
                  {f === 'all' ? '전체' : '처리 필요'}
                </button>
              ))}
            </div>
          } />
          <ul className="divide-y divide-line">
            {list.map((m) => (
              <li key={m.id}>
                <button onClick={() => setSel(m.id)} className={clsx('w-full cursor-pointer px-4 py-3 text-left hover:bg-surface2', sel === m.id && 'bg-accentsoft/60')}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">{m.from.name}</span>
                    <span className="shrink-0 text-xs text-muted">{fmtTime(m.receivedAt)}</span>
                  </div>
                  <div className="mt-0.5 truncate text-sm text-muted">{m.subject}</div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <Badge tone={labelMeta[m.label].tone}>{labelMeta[m.label].text} {Math.round(m.confidence * 100)}%</Badge>
                    <Badge tone={statusMeta[m.status].tone}>{statusMeta[m.status].text}</Badge>
                    {m.injectionFlagged && <Badge tone="bad"><ShieldAlert size={12} /> 인젝션</Badge>}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </Card>

        {current ? <Detail key={current.id} mail={current} busy={act.isPending} onAct={(a) => act.mutate({ id: current.id, a })} /> : <Card className="p-8 text-center text-muted">메일을 선택하세요</Card>}
      </div>
    </>
  )
}

function Detail({ mail, onAct, busy }: { mail: Mail; onAct: (a: ReplyAction) => void; busy: boolean }) {
  const [instr, setInstr] = useState('')
  const actionable = mail.status === 'pending_approval'
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <Card>
        <CardHeader title={mail.subject} right={<Link to={`/runs/${mail.runId}`} className="text-xs text-accent hover:underline">실행 트레이스 보기 →</Link>} />
        <div className="px-4 py-3 text-sm">
          <div className="text-muted">{mail.from.name} &lt;{mail.from.email}&gt; · {fmtTime(mail.receivedAt)}</div>
          <pre className="mt-3 whitespace-pre-wrap font-sans leading-relaxed">{mail.body}</pre>
        </div>
      </Card>

      {mail.injectionFlagged && (
        <div className="flex gap-2 rounded-xl border border-bad/40 bg-badsoft p-3 text-sm text-bad">
          <ShieldAlert size={18} className="mt-0.5 shrink-0" />
          <div><b>프롬프트 인젝션 의심.</b> 본문에 AI에게 내리는 지시문이 포함되어 있어 초안 생성이 차단되었고 경보가 기록되었습니다.</div>
        </div>
      )}

      <Card>
        <CardHeader title="분류 결과 (Triage)" right={<Badge tone={labelMeta[mail.label].tone}>{labelMeta[mail.label].text}</Badge>} />
        <div className="px-4 py-3 text-sm">
          <div className="flex items-center gap-3">
            <div className="h-2 w-40 overflow-hidden rounded-full bg-surface2">
              <div className={clsx('h-full', mail.confidence < 0.6 ? 'bg-bad' : 'bg-accent')} style={{ width: `${mail.confidence * 100}%` }} />
            </div>
            <span className="tabular-nums">{(mail.confidence * 100).toFixed(0)}%</span>
            {mail.confidence < 0.6 && <Badge tone="bad"><AlertTriangle size={12} /> 임계값 0.6 미만</Badge>}
          </div>
          <p className="mt-2 text-muted">{mail.reason}</p>
          {mail.status === 'needs_human' && (
            <div className="mt-3 flex gap-2">
              <Button variant="primary" onClick={() => onAct({ type: 'classify', reply_needed: true })}>회신 필요로 처리</Button>
              <Button onClick={() => onAct({ type: 'classify', reply_needed: false })}>회신 불필요</Button>
            </div>
          )}
        </div>
      </Card>

      {mail.draft && (
        <Card>
          <CardHeader title={`회신 초안 v${mail.draft.version}`} right={
            mail.draft.review.passed ? <Badge tone="ok"><Check size={12} /> Reviewer 통과</Badge> : <Badge tone="warn">검수 지적 {mail.draft.review.issues.length}건</Badge>
          } />
          <div className="px-4 py-3">
            <pre className="whitespace-pre-wrap rounded-lg bg-surface2 p-3 font-sans text-sm leading-relaxed">{mail.draft.body}</pre>
            <div className="mt-2 text-xs text-muted">Gmail 초안함에 저장됨 · 발송은 Gmail에서 직접 수행합니다.</div>
            {actionable && (
              <div className="mt-4 flex flex-col gap-3">
                <div className="flex gap-2">
                  <input value={instr} onChange={(e) => setInstr(e.target.value)} placeholder="수정 요청 (예: 더 격식 있게, 금요일 → 목요일)"
                    className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-sm outline-none focus:border-accent" />
                  <Button disabled={!instr || busy} onClick={() => { onAct({ type: 'revise', instruction: instr }); setInstr('') }}><Pencil size={14} /> 수정 요청</Button>
                </div>
                <div className="flex gap-2">
                  <Button variant="primary" disabled={busy} onClick={() => onAct({ type: 'approve' })}><Check size={14} /> 승인 (초안 유지)</Button>
                  <Button variant="danger" disabled={busy} onClick={() => onAct({ type: 'discard' })}><Trash2 size={14} /> 폐기</Button>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  )
}
