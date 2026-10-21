import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /codefix (see seatunnel_agent.agents.ai.code_fix.api)
export default makeViteConfig({ base: '/codefix/', apiPath: '/api/codefix', url: import.meta.url })
