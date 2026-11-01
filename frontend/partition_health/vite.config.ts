import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/partitionhealth/',
  apiPath: '/api/partitionhealth',
  url: import.meta.url,
})
