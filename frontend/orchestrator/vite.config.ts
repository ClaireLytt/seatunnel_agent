import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /orchestrator (see seatunnel_agent.agents.ai.orchestrator.api)
export default makeViteConfig({ base: '/orchestrator/', apiPath: '/api/orchestrator', url: import.meta.url })
