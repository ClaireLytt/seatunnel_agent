import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /impact (see seatunnel_agent.agents.data.change_impact.api)
export default makeViteConfig({ base: '/impact/', apiPath: '/api/lineage', url: import.meta.url })
