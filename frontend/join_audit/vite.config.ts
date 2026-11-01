import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/joinaudit/',
  apiPath: '/api/joinaudit',
  url: import.meta.url,
})
