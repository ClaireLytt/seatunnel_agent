import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /promptlab (see seatunnel_agent.agents.ai.prompt_lab.api)
export default makeViteConfig({ base: '/promptlab/', apiPath: '/api/promptlab', url: import.meta.url })
