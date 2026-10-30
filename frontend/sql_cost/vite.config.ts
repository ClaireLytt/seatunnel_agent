import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/sqlcost/',
  apiPath: '/api/sqlcost',
  url: import.meta.url,
})
