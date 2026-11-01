import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/fieldusage/',
  apiPath: '/api/fieldusage',
  url: import.meta.url,
})
