import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/rtlatency/',
  apiPath: '/api/rtlatency',
  url: import.meta.url,
})
