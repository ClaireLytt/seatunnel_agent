import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({
  base: '/ddlevolve/',
  apiPath: '/api/ddlevolve',
  url: import.meta.url,
})
