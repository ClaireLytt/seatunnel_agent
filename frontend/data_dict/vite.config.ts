import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/datadict/',
  apiPath: '/api/datadict',
  url: import.meta.url,
})
