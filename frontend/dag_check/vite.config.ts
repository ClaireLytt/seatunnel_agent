import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /dagcheck (see seatunnel_agent.agents.data.dag_check.api)
export default makeViteConfig({ base: '/dagcheck/', apiPath: '/api/dagcheck', url: import.meta.url })
