import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /dataskew (see seatunnel_agent.agents.data.data_skew.api)
export default makeViteConfig({ base: '/dataskew/', apiPath: '/api/skew', url: import.meta.url })
