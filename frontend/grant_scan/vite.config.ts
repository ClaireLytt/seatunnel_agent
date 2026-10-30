import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /grants (see agents.data.grant_scan.api)
export default makeViteConfig({ base: '/grants/', apiPath: '/api/grants', url: import.meta.url })
