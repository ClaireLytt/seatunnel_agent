import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/slowquery/',
  apiPath: '/api/slowquery',
  url: import.meta.url,
})
