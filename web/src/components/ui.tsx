import clsx from 'clsx'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { Label, MailStatus, RiskTier } from '@/api/types'

type Tone = 'neutral' | 'accent' | 'ok' | 'warn' | 'bad' | 'sup'
const tones: Record<Tone, string> = {
  neutral: 'bg-surface2 text-muted',
  accent: 'bg-accentsoft text-accent',
  ok: 'bg-oksoft text-ok',
  warn: 'bg-warnsoft text-warn',
  bad: 'bg-badsoft text-bad',
  sup: 'bg-supsoft text-sup',
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={clsx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap', tones[tone])}>{children}</span>
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={clsx('rounded-xl border border-line bg-surface', className)}>{children}</section>
}

export function CardHeader({ title, right }: { title: ReactNode; right?: ReactNode }) {
  return (
    <header className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      {right}
    </header>
  )
}

export function Button({ variant = 'default', className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'primary' | 'danger' }) {
  return (
    <button
      {...p}
      className={clsx(
        'inline-flex items-center justify-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50 cursor-pointer',
        variant === 'primary' && 'border-accent bg-accent text-white hover:opacity-90',
        variant === 'danger' && 'border-line text-bad hover:bg-badsoft',
        variant === 'default' && 'border-line bg-surface hover:bg-surface2',
        className,
      )}
    />
  )
}

export const labelMeta: Record<Label, { text: string; tone: Tone }> = {
  reply_needed: { text: '회신 필요', tone: 'accent' },
  fyi: { text: 'FYI', tone: 'neutral' },
  newsletter: { text: '뉴스레터', tone: 'neutral' },
  spam: { text: '스팸', tone: 'bad' },
  auto: { text: '자동 발송', tone: 'neutral' },
}
export const statusMeta: Record<MailStatus, { text: string; tone: Tone }> = {
  pending_approval: { text: '승인 대기', tone: 'warn' },
  needs_human: { text: '사람 확인 필요', tone: 'bad' },
  approved: { text: '승인됨', tone: 'ok' },
  discarded: { text: '폐기됨', tone: 'neutral' },
  skipped: { text: '처리 불필요', tone: 'neutral' },
}
export const riskMeta: Record<RiskTier, { text: string; tone: Tone }> = {
  low: { text: 'low', tone: 'ok' },
  medium: { text: 'medium', tone: 'warn' },
  high: { text: 'high · 항상 HITL', tone: 'bad' },
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  )
}

export function PageHeader({ title, desc, right }: { title: string; desc?: string; right?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {desc && <p className="mt-1 text-sm text-muted">{desc}</p>}
      </div>
      {right}
    </div>
  )
}

export const fmtTime = (iso: string) =>
  new Intl.DateTimeFormat('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
