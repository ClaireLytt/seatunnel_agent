import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served by FastAPI at /webtask (see seatunnel_agent.agents.ai.web_task.api)
export default defineConfig({
  base: '/webtask/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared/src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api/webtask': 'http://127.0.0.1:7860',
    },
  },
  build: {
    outDir: 'dist',
  },
})
