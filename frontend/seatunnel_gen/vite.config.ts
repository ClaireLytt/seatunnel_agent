import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/seatunnelgen/',
  apiPath: '/api/seatunnelgen',
  url: import.meta.url,
})
