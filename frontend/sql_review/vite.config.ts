import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /sqlreview (see seatunnel_agent.agents.data.sql_review.api)
export default makeViteConfig({ base: '/sqlreview/', apiPath: '/api/sql_review', url: import.meta.url })
