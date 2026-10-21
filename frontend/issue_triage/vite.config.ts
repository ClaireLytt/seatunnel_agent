import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /triage (see seatunnel_agent.agents.ai.issue_triage.api)
export default makeViteConfig({ base: '/triage/', apiPath: '/api/triage', url: import.meta.url })
