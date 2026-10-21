import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /transpile (see seatunnel_agent.agents.data.sql_transpile.api)
export default makeViteConfig({ base: '/transpile/', apiPath: '/api/transpile', url: import.meta.url })
