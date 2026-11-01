import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/schemaalign/',
  apiPath: '/api/schemaalign',
  url: import.meta.url,
})
