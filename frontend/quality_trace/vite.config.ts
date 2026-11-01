import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/qualitytrace/',
  apiPath: '/api/qualitytrace',
  url: import.meta.url,
})
