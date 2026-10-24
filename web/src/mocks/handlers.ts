import { http, HttpResponse, sse } from 'msw'
import type { Mail, ReplyAction } from '@/api/types'
import { agents, experiments, mails, runs } from './data'
import { makeEvent, script } from './live'

// 변이(승인/폐기/수정)를 메모리에 반영해 화면 흐름을 실제처럼 시연
const db: Mail[] = structuredClone(mails)

let seq = 0
const subjects = ['Quick question about the onboarding timeline']

export const handlers = [
  // 실시간 이벤트 스트림(SSE). 실제로는 LangGraph 스트림을 그대로 중계한다.
  sse('/api/events', ({ client, request }) => {
    // 리졸버를 즉시 반환해야 응답 헤더가 전송된다 → 스트리밍은 분리 실행
    let closed = false
    request.signal.addEventListener('abort', () => { closed = true })
    void (async () => {
      let n = 0
      while (!closed) {
        const runId = `live-${++n}`
        for (const step of script(subjects[n % subjects.length])) {
          await new Promise((r) => setTimeout(r, step[0]))
          if (closed) return
          client.send({ data: JSON.stringify(makeEvent(++seq, runId, step)) })
        }
        await new Promise((r) => setTimeout(r, 2500))
      }
    })()
  }),
  http.get('/api/mails', () => HttpResponse.json(db)),
  http.get('/api/mails/:id', ({ params }) => {
    const mail = db.find((x) => x.id === params.id)
    return mail ? HttpResponse.json(mail) : new HttpResponse(null, { status: 404 })
  }),
  http.post('/api/mails/:id/actions', async ({ params, request }) => {
    const mail = db.find((x) => x.id === params.id)
    if (!mail) return new HttpResponse(null, { status: 404 })
    const a = (await request.json()) as ReplyAction
    if (a.type === 'approve') mail.status = 'approved'
    if (a.type === 'classify') mail.status = a.reply_needed ? 'pending_approval' : 'skipped'
    if (a.type === 'discard') { mail.status = 'discarded'; mail.draft = undefined }
    if (a.type === 'revise' && mail.draft) {
      mail.draft = { ...mail.draft, version: mail.draft.version + 1, body: `${mail.draft.body}\n\n(수정 요청 반영: ${a.instruction ?? ''})` }
    }
    return HttpResponse.json(mail)
  }),
  http.get('/api/runs/:id', ({ params }) => {
    const run = runs.find((x) => x.id === params.id)
    return run ? HttpResponse.json(run) : new HttpResponse(null, { status: 404 })
  }),
  http.get('/api/agents', () => HttpResponse.json(agents)),
  http.get('/api/experiments', () => HttpResponse.json(experiments)),
]
