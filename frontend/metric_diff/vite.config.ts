import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /metricdiff (see seatunnel_agent.agents.data.metric_diff.api)
export default makeViteConfig({ base: '/metricdiff/', apiPath: '/api/metricdiff', url: import.meta.url })
