import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /uitest (see seatunnel_agent.agents.devops.ui_testing.api)
export default makeViteConfig({ base: '/uitest/', apiPath: '/api/uitest', url: import.meta.url })
