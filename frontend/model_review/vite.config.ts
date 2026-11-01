import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/modelreview/',
  apiPath: '/api/modelreview',
  url: import.meta.url,
})
