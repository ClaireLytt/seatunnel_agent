import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /migrate (see seatunnel_agent.agents.data.config_migrate.api)
export default makeViteConfig({ base: '/migrate/', apiPath: '/api/config_migrate', url: import.meta.url })
