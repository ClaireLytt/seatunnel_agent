import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/dupcheck/',
  apiPath: '/api/dupcheck',
  url: import.meta.url,
})
