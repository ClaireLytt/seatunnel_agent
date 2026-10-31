import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/topicschema/',
  apiPath: '/api/topicschema',
  url: import.meta.url,
})
