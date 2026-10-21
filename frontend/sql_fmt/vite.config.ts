import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /sqlfmt (see seatunnel_agent.agents.data.sql_fmt.api)
export default makeViteConfig({ base: '/sqlfmt/', apiPath: '/api/sqlfmt', url: import.meta.url })
