import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/incidentreview/',
  apiPath: '/api/incidentreview',
  url: import.meta.url,
})
