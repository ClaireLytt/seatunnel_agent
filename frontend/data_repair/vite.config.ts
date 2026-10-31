import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/datarepair/',
  apiPath: '/api/datarepair',
  url: import.meta.url,
})
