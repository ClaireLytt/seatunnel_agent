import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /secretscan (see seatunnel_agent.agents.devops.secret_scan.api)
export default makeViteConfig({ base: '/secretscan/', apiPath: '/api/secretscan', url: import.meta.url })
