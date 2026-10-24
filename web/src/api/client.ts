import type { AgentManifest, Experiment, Mail, ReplyAction, Run } from './types'

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  mails: () => http<Mail[]>('/api/mails'),
  mail: (id: string) => http<Mail>(`/api/mails/${id}`),
  act: (id: string, action: ReplyAction) =>
    http<Mail>(`/api/mails/${id}/actions`, { method: 'POST', body: JSON.stringify(action) }),
  run: (id: string) => http<Run>(`/api/runs/${id}`),
  agents: () => http<AgentManifest[]>('/api/agents'),
  experiments: () => http<Experiment[]>('/api/experiments'),
}
