import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/flinkdiag/',
  apiPath: '/api/flinkdiag',
  url: import.meta.url,
})
