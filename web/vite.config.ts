import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'
import { fileURLToPath } from 'node:url'

export default defineConfig(({ mode }) => {
  // 프로젝트 루트 .env 의 API_TOKEN 을 프록시가 헤더로 주입 (브라우저 번들에는 포함되지 않음)
  const token = loadEnv(mode, '..', '').API_TOKEN ?? ''
  return {
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  // 실제 개발 시 FastAPI 백엔드로 프록시 (목업 단계에서는 MSW가 가로챔)
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true, headers: { 'X-API-Key': token } } } },
  }
})
