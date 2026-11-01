import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/slaboard/',
  apiPath: '/api/slaboard',
  url: import.meta.url,
})
