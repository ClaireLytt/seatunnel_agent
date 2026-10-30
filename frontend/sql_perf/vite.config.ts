import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/sqlperf/',
  apiPath: '/api/sqlperf',
  url: import.meta.url,
})
