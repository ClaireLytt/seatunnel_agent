import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served by FastAPI at /datacompare (see seatunnel_agent.agents.data.data_comparison.api)
export default defineConfig({
  base: '/datacompare/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared/src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api/datacompare': 'http://127.0.0.1:7860',
    },
  },
  build: {
    outDir: 'dist',
  },
})
