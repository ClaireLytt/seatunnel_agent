import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /ciinspect (see seatunnel_agent.agents.devops.ci_inspect.api)
export default makeViteConfig({ base: '/ciinspect/', apiPath: '/api/ciinspect', url: import.meta.url })
