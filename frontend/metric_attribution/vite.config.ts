import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/metricattribution/',
  apiPath: '/api/metricattribution',
  url: import.meta.url,
})
