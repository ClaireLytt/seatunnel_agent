import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/avro2ddl/',
  apiPath: '/api/avro2ddl',
  url: import.meta.url,
})
