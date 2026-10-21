import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /datacompare (see seatunnel_agent.agents.data.data_comparison.api)
export default makeViteConfig({ base: '/datacompare/', apiPath: '/api/datacompare', url: import.meta.url })
