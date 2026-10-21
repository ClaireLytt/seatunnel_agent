import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export interface MakeViteConfigOptions {
  /** Public base path the app is served at, e.g. '/docqa/'. */
  base: string
  /** API prefix proxied to the FastAPI backend in dev, e.g. '/api/docqa'. */
  apiPath: string
  /**
   * The caller's `import.meta.url` (the workspace vite.config.ts), used to
   * resolve the '@' and '@shared' aliases relative to that workspace.
   */
  url: string
}

export function makeViteConfig({ base, apiPath, url }: MakeViteConfigOptions) {
  return defineConfig({
    base,
    plugins: [react()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', url)),
        '@shared': fileURLToPath(new URL('../shared/src', url)),
      },
    },
    server: {
      proxy: {
        [apiPath]: 'http://127.0.0.1:7860',
      },
    },
    build: {
      outDir: 'dist',
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            if (!id.includes('node_modules')) return undefined
            if (/node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) {
              return 'vendor-react'
            }
            if (/node_modules[\\/](recharts|d3-[^\\/]+|victory-vendor|internmap|delaunator|robust-predicates)[\\/]/.test(id)) {
              return 'vendor-charts'
            }
            return undefined
          },
        },
      },
    },
  })
}
