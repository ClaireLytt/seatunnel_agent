import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/rollbackplan/',
  apiPath: '/api/rollbackplan',
  url: import.meta.url,
})
