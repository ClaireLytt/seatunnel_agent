import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /governance (see agents.data.governance_overview)
export default makeViteConfig({ base: '/governance/', apiPath: '/api', url: import.meta.url })
