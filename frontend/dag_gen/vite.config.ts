import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/daggen/',
  apiPath: '/api/daggen',
  url: import.meta.url,
})
