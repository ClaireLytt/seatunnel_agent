import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/dqrulegen/',
  apiPath: '/api/dqrulegen',
  url: import.meta.url,
})
