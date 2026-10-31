import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/maskpreview/',
  apiPath: '/api/maskpreview',
  url: import.meta.url,
})
