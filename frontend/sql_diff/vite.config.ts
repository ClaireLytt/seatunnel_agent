import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/sqldiff/',
  apiPath: '/api/sqldiff',
  url: import.meta.url,
})
