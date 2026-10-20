import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served by FastAPI at /llmeval (see seatunnel_agent.agents.ai.llm_eval.api)
export default defineConfig({
  base: '/llmeval/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared/src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api/llmeval': 'http://127.0.0.1:7860',
    },
  },
  build: {
    outDir: 'dist',
  },
})
