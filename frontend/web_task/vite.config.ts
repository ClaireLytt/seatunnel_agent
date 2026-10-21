import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /webtask (see seatunnel_agent.agents.ai.web_task.api)
export default makeViteConfig({ base: '/webtask/', apiPath: '/api/webtask', url: import.meta.url })
