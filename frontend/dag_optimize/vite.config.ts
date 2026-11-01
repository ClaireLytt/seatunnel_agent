import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/dagopt/',
  apiPath: '/api/dagopt',
  url: import.meta.url,
})
