import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/indexadvisor/',
  apiPath: '/api/indexadvisor',
  url: import.meta.url,
})
