import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/cdcdiag/',
  apiPath: '/api/cdcdiag',
  url: import.meta.url,
})
