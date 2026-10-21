import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /lineage (see seatunnel_agent.agents.data.data_lineage.api)
export default makeViteConfig({ base: '/lineage/', apiPath: '/api/lineage', url: import.meta.url })
