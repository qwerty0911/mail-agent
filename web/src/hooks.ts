import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import type { LiveEvent } from '@/api/types'

export type NodeState = 'idle' | 'active' | 'done' | 'retry' | 'error' | 'waiting'
interface LiveState {
  events: LiveEvent[]
  nodes: Record<string, NodeState>
  runId?: string
  subject?: string
  draft: string
  finished: boolean
  startedAt?: number
}
const init: LiveState = { events: [], nodes: {}, draft: '', finished: false }

function reduce(s: LiveState, e: LiveEvent): LiveState {
  const events = [...s.events, e].slice(-300)
  if (e.type === 'run_started') return { ...init, events, runId: e.runId, subject: e.subject, startedAt: Date.parse(e.ts) }
  const nodes = { ...s.nodes }
  let draft = s.draft
  if (e.type === 'node_started') {
    nodes[e.actor] = 'active'
    if (e.actor === 'drafting') draft = ''
  }
  if (e.type === 'node_finished' && nodes.tool_gateway === 'active') nodes.tool_gateway = 'done'
  if (e.type === 'node_finished') nodes[e.actor] = e.status === 'retry' ? 'retry' : e.status === 'error' ? 'error' : 'done'
  if (e.type === 'tool_call') nodes[e.actor] = 'active'
  if (e.type === 'hitl_wait') nodes[e.actor] = 'waiting'
  if (e.type === 'token' && e.delta) draft += e.delta
  if (e.type === 'run_finished') { nodes.supervisor = 'done'; return { ...s, events, nodes, draft, finished: true } }
  return { ...s, events, nodes, draft }
}

export function useLiveEvents() {
  const [state, dispatch] = useReducer(reduce, init)
  const [connected, setConnected] = useState(false)
  const [paused, setPaused] = useState(false)
  const pausedRef = useRef(false)
  pausedRef.current = paused

  useEffect(() => {
    const es = new EventSource('/api/events')
    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)
    es.onmessage = (m) => { if (!pausedRef.current) dispatch(JSON.parse(m.data) as LiveEvent) }
    return () => es.close()
  }, [])

  return { ...state, connected, paused, togglePause: useCallback(() => setPaused((p) => !p), []) }
}
