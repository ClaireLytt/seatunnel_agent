import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/alertstorm/',
  apiPath: '/api/alertstorm',
  url: import.meta.url,
})
