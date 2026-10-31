import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/storagecost/',
  apiPath: '/api/storagecost',
  url: import.meta.url,
})
