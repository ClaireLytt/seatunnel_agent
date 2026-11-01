import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/compactplan/',
  apiPath: '/api/compactplan',
  url: import.meta.url,
})
