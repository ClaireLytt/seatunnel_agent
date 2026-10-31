import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/capacityforecast/',
  apiPath: '/api/capacityforecast',
  url: import.meta.url,
})
