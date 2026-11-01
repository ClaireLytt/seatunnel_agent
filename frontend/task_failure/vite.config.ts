import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/taskfailure/',
  apiPath: '/api/taskfailure',
  url: import.meta.url,
})
