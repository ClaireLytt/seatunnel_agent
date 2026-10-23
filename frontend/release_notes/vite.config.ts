import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({ base: '/release/', apiPath: '/api/release', url: import.meta.url })
