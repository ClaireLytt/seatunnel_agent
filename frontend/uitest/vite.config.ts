import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// Served by FastAPI at /uitest (see seatunnel_agent.agents.devops.ui_testing.api)
export default defineConfig({
  base: '/uitest/',
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'UI Testing Agent',
        short_name: 'UITest',
        start_url: '/uitest/',
        display: 'standalone',
        background_color: '#f7f6f2',
        theme_color: '#2b2e8c',
        icons: [],
      },
    }),
  ],
  server: {
    proxy: {
      '/api/uitest': 'http://127.0.0.1:7860',
    },
  },
  build: {
    outDir: 'dist',
  },
})
