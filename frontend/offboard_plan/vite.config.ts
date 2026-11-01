import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/offboardplan/',
  apiPath: '/api/offboardplan',
  url: import.meta.url,
})
