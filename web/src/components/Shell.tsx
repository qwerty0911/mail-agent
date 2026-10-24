import { NavLink, Outlet } from 'react-router-dom'
import { Activity, Radio, Bot, FlaskConical, Inbox, MessageSquare, ShieldCheck } from 'lucide-react'
import clsx from 'clsx'

const nav = [
  { to: '/', label: '검토 큐', icon: Inbox, end: true },
  { to: '/live', label: '실시간 모니터', icon: Radio },
  { to: '/runs', label: '실행 트레이스', icon: Activity },
  { to: '/agents', label: '에이전트 레지스트리', icon: Bot },
  { to: '/evals', label: '평가 (LangSmith)', icon: FlaskConical },
  { to: '/messenger', label: '메신저 미리보기', icon: MessageSquare },
]

export function Shell() {
  return (
    <div className="flex h-full">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-line bg-surface md:flex">
        <div className="px-5 py-4">
          <div className="text-base font-semibold">Mail Agent</div>
          <div className="text-xs text-muted">Supervisor Console</div>
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 px-3">
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) => clsx('flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm', isActive ? 'bg-accentsoft font-medium text-accent' : 'text-muted hover:bg-surface2')}>
              <Icon size={16} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="m-3 rounded-lg bg-oksoft p-3 text-xs text-ok">
          <div className="flex items-center gap-1.5 font-medium"><ShieldCheck size={14} /> 발송 권한 없음</div>
          <div className="mt-1 opacity-80">gmail.readonly + compose 만 사용. 초안만 저장됩니다.</div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <nav className="flex gap-1 overflow-x-auto border-b border-line bg-surface px-3 py-2 md:hidden">
          {nav.map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => clsx('whitespace-nowrap rounded-lg px-3 py-1.5 text-sm', isActive ? 'bg-accentsoft text-accent' : 'text-muted')}>{label}</NavLink>
          ))}
        </nav>
        <main className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6"><Outlet /></main>
      </div>
    </div>
  )
}
