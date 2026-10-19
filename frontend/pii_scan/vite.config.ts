import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served by FastAPI at /pii (see seatunnel_agent.agents.data.pii_scan.api)
export default defineConfig({
  base: '/pii/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared/src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api/pii': 'http://127.0.0.1:7860',
    },
  },
  build: {
    outDir: 'dist',
  },
})
