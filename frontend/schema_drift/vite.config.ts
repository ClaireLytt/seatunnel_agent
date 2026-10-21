import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /schemadrift (see seatunnel_agent.agents.data.schema_drift.api)
export default makeViteConfig({ base: '/schemadrift/', apiPath: '/api/schemadrift', url: import.meta.url })
