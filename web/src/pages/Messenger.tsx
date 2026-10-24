import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { Card, PageHeader, labelMeta } from '@/components/ui'

// Hermes Gateway가 Telegram/Slack으로 보내는 승인 카드 형식. 백엔드 notify 노드의 출력 스키마가 곧 이 컴포넌트의 props.
export default function Messenger() {
  const { data: mails = [] } = useQuery({ queryKey: ['mails'], queryFn: api.mails })
  const [kind, setKind] = useState<'telegram' | 'slack'>('telegram')
  const m = mails.find((x) => x.draft && x.status === 'pending_approval') ?? mails[0]
  const hold = mails.find((x) => x.status === 'needs_human')

  return (
    <>
      <PageHeader title="메신저 미리보기" desc="Hermes Gateway가 사용자에게 보내는 알림·승인 카드입니다. 버튼 응답은 MCP 도구(approve_draft / discard_draft)로 Supervisor에 전달됩니다."
        right={
          <div className="flex rounded-lg border border-line bg-surface p-0.5 text-sm">
            {(['telegram', 'slack'] as const).map((k) => (
              <button key={k} onClick={() => setKind(k)} className={`cursor-pointer rounded-md px-3 py-1 ${kind === k ? 'bg-accentsoft text-accent' : 'text-muted'}`}>{k === 'telegram' ? 'Telegram' : 'Slack'}</button>
            ))}
          </div>
        } />
      <Card className="mx-auto max-w-md bg-surface2 p-4">
        <div className="mb-3 text-center text-xs text-muted">오늘 08:43</div>
        {m && (
          <Bubble kind={kind}>
            <div className="text-xs text-muted">📬 {labelMeta[m.label].text} · 신뢰도 {Math.round(m.confidence * 100)}%</div>
            <div className="mt-1 font-semibold">{m.subject}</div>
            <div className="text-xs text-muted">From {m.from.name} · 사유: {m.reason}</div>
            {m.draft && (
              <>
                <div className="mt-2 text-xs text-muted">✅ Reviewer 통과 · 초안 v{m.draft.version} (Gmail 초안함 저장됨)</div>
                <blockquote className="mt-1 whitespace-pre-wrap border-l-2 border-accent pl-2 text-sm">{m.draft.body.slice(0, 160)}…</blockquote>
              </>
            )}
            <Buttons kind={kind} items={['✅ 승인', '✏️ 수정 요청', '🗑 폐기']} />
          </Bubble>
        )}
        {hold && (
          <Bubble kind={kind}>
            <div className="text-xs text-muted">❓ 사람 확인 필요 · 신뢰도 {Math.round(hold.confidence * 100)}%</div>
            <div className="mt-1 font-semibold">{hold.subject}</div>
            <div className="text-xs text-muted">{hold.reason}</div>
            <Buttons kind={kind} items={['회신 필요', '회신 불필요']} />
          </Bubble>
        )}
        <Bubble kind={kind}>
          <div className="text-xs text-muted">🛡 보안 경보</div>
          <div className="mt-1 text-sm">프롬프트 인젝션 의심 메일 1건을 차단했습니다. 초안은 생성되지 않았습니다.</div>
        </Bubble>
      </Card>
    </>
  )
}

function Bubble({ kind, children }: { kind: 'telegram' | 'slack'; children: React.ReactNode }) {
  return (
    <div className={`mb-3 ${kind === 'slack' ? 'flex gap-2' : ''}`}>
      {kind === 'slack' && <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-md bg-sup text-xs font-bold text-white">M</div>}
      <div className={`${kind === 'telegram' ? 'rounded-2xl rounded-tl-sm border border-line bg-surface p-3' : 'flex-1'} text-sm`}>
        {kind === 'slack' && <div className="mb-1 text-sm font-semibold">Mail Agent <span className="text-xs font-normal text-muted">APP</span></div>}
        {children}
      </div>
    </div>
  )
}

function Buttons({ kind, items }: { kind: 'telegram' | 'slack'; items: string[] }) {
  return (
    <div className={`mt-3 flex gap-2 ${kind === 'telegram' ? 'flex-col' : 'flex-wrap'}`}>
      {items.map((t) => (
        <button key={t} className={`cursor-pointer border border-line text-sm hover:bg-accentsoft ${kind === 'telegram' ? 'rounded-lg bg-accentsoft py-1.5 text-accent' : 'rounded-md bg-surface px-3 py-1'}`}>{t}</button>
      ))}
    </div>
  )
}
