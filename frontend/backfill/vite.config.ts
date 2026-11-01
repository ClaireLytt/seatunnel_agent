import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/backfill/',
  apiPath: '/api/backfill',
  url: import.meta.url,
})
