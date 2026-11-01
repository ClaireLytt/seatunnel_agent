import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/partitionplan/',
  apiPath: '/api/partitionplan',
  url: import.meta.url,
})
