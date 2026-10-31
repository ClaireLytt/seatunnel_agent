import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/backfillsql/',
  apiPath: '/api/backfillsql',
  url: import.meta.url,
})
