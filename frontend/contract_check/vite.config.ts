import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /contract (see agents.data.contract_check.api)
export default makeViteConfig({ base: '/contract/', apiPath: '/api/contract', url: import.meta.url })
