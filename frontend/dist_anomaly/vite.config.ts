import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/distanomaly/',
  apiPath: '/api/distanomaly',
  url: import.meta.url,
})
