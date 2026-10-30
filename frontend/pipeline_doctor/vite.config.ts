import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/pipedoctor/',
  apiPath: '/api/pipedoctor',
  url: import.meta.url,
})
