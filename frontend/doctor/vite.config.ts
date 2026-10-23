import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({ base: '/doctor/', apiPath: '/api/doctor', url: import.meta.url })
