import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/datavolatility/',
  apiPath: '/api/datavolatility',
  url: import.meta.url,
})
