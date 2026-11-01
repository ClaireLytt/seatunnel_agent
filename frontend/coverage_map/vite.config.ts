import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/coveragemap/',
  apiPath: '/api/coveragemap',
  url: import.meta.url,
})
