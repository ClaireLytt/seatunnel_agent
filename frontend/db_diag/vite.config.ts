import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/dbdiag/',
  apiPath: '/api/dbdiag',
  url: import.meta.url,
})
