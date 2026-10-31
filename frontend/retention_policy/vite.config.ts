import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/retention/',
  apiPath: '/api/retention',
  url: import.meta.url,
})
