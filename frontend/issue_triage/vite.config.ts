import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served by FastAPI at /triage (see seatunnel_agent.agents.ai.issue_triage.api)
export default defineConfig({
  base: '/triage/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared/src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api/triage': 'http://127.0.0.1:7860',
    },
  },
  build: {
    outDir: 'dist',
  },
})
