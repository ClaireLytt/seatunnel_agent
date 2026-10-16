import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served at /text2sql (route swap #67); legacy Gradio at /text2sql-legacy.
export default defineConfig({
  base: '/text2sql/',
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
