import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/rtoffline/',
  apiPath: '/api/rtoffline',
  url: import.meta.url,
})
