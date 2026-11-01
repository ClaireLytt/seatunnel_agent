import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/rerun/',
  apiPath: '/api/rerun',
  url: import.meta.url,
})
