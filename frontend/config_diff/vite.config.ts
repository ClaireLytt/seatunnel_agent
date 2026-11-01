import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/configdiff/',
  apiPath: '/api/configdiff',
  url: import.meta.url,
})
