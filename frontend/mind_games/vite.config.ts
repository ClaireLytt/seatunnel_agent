import { makeViteConfig } from '../shared/vite.base'

// Served statically at /games (no API — everything runs in the browser)
export default makeViteConfig({ base: '/games/', apiPath: '/api/__none__', url: import.meta.url })
