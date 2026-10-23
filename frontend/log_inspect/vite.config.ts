import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({ base: '/loginspect/', apiPath: '/api/loginspect', url: import.meta.url })
