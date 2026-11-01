import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/mockdata/',
  apiPath: '/api/mockdata',
  url: import.meta.url,
})
