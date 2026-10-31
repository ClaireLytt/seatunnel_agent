import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/layercheck/',
  apiPath: '/api/layercheck',
  url: import.meta.url,
})
