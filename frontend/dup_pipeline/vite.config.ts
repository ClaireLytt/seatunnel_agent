import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/duppipeline/',
  apiPath: '/api/duppipeline',
  url: import.meta.url,
})
