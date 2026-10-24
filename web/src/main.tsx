import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 5_000 } } })

async function boot() {
  // 목업 단계: API를 MSW로 대체. 실제 백엔드 연결 시 VITE_USE_MOCK=false 로 끈다.
  if (import.meta.env.VITE_USE_MOCK !== 'false') {
    const { worker } = await import('./mocks/browser')
    await worker.start({ quiet: true })
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={qc}>
        <BrowserRouter><App /></BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}
void boot()
