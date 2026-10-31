import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/assetvalue/',
  apiPath: '/api/assetvalue',
  url: import.meta.url,
})
