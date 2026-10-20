import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served by FastAPI at /codefix (see seatunnel_agent.agents.ai.code_fix.api)
export default defineConfig({
  base: '/codefix/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared/src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api/codefix': 'http://127.0.0.1:7860',
    },
  },
  build: {
    outDir: 'dist',
  },
})
