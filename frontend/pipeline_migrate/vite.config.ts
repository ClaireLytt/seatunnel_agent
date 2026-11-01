import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/pipemigrate/',
  apiPath: '/api/pipemigrate',
  url: import.meta.url,
})
