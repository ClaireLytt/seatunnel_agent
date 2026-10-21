import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /conflint (see seatunnel_agent.agents.data.config_lint.api)
export default makeViteConfig({ base: '/conflint/', apiPath: '/api/conflint', url: import.meta.url })
