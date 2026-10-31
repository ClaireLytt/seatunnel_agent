import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/scheduleadvisor/',
  apiPath: '/api/scheduleadvisor',
  url: import.meta.url,
})
