import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/suites/',
  apiPath: '/api/suites',
  url: import.meta.url,
})
