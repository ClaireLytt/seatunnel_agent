import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /hygiene (see seatunnel_agent.agents.data.lineage_hygiene.api)
export default makeViteConfig({ base: '/hygiene/', apiPath: '/api/hygiene', url: import.meta.url })
