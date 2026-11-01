import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/syncstrategy/',
  apiPath: '/api/syncstrategy',
  url: import.meta.url,
})
