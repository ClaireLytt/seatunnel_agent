import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/grantreview/',
  apiPath: '/api/grantreview',
  url: import.meta.url,
})
