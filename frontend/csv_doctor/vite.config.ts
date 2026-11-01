import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/csvdoctor/',
  apiPath: '/api/csvdoctor',
  url: import.meta.url,
})
