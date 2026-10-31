import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/assetsearch/',
  apiPath: '/api/assetsearch',
  url: import.meta.url,
})
