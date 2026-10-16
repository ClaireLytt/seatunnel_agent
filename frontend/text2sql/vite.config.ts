import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev route until the route swap ticket (#67): served at /text2sql-next.
export default defineConfig({
  base: '/text2sql-next/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared/src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api/text2sql': 'http://127.0.0.1:7860',
    },
  },
})
