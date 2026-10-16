import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served by FastAPI at /uitest (see seatunnel_agent.agents.devops.ui_testing.api)
export default defineConfig({
  base: '/uitest/',
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    proxy: {
      '/api/uitest': 'http://127.0.0.1:7860',
    },
  },
  build: {
    outDir: 'dist',
  },
})
