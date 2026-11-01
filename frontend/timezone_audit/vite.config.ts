import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/timezoneaudit/',
  apiPath: '/api/timezoneaudit',
  url: import.meta.url,
})
