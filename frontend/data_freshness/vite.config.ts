import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/freshness/',
  apiPath: '/api/freshness',
  url: import.meta.url,
})
