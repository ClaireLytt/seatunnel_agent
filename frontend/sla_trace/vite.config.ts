import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/slatrace/',
  apiPath: '/api/slatrace',
  url: import.meta.url,
})
