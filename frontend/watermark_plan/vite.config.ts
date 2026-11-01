import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/watermarkplan/',
  apiPath: '/api/watermarkplan',
  url: import.meta.url,
})
