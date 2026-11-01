import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/sampleprofile/',
  apiPath: '/api/sampleprofile',
  url: import.meta.url,
})
