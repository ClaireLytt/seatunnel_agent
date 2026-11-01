import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/contractgen/',
  apiPath: '/api/contractgen',
  url: import.meta.url,
})
