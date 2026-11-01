import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/kafkalag/',
  apiPath: '/api/kafkalag',
  url: import.meta.url,
})
