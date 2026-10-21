import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /testgen (see seatunnel_agent.agents.data.sql_testgen.api)
export default makeViteConfig({ base: '/testgen/', apiPath: '/api/testgen', url: import.meta.url })
