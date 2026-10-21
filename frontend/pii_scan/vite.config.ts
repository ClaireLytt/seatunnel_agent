import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /pii (see seatunnel_agent.agents.data.pii_scan.api)
export default makeViteConfig({ base: '/pii/', apiPath: '/api/pii', url: import.meta.url })
