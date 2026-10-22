import { makeViteConfig } from '../shared/vite.base'

export default makeViteConfig({ base: '/depcheck/', apiPath: '/api/depcheck', url: import.meta.url })
