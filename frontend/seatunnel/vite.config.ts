import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /seatunnel (see seatunnel_agent.agents.data.seatunnel.api)
export default makeViteConfig({ base: '/seatunnel/', apiPath: '/api/seatunnel', url: import.meta.url })
