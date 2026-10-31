import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/dagconflict/',
  apiPath: '/api/dagconflict',
  url: import.meta.url,
})
