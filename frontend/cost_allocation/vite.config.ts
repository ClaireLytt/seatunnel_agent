import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/costalloc/',
  apiPath: '/api/costalloc',
  url: import.meta.url,
})
