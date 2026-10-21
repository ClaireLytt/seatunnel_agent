import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /llmcost (see seatunnel_agent.agents.ai.llm_cost.api)
export default makeViteConfig({ base: '/llmcost/', apiPath: '/api/llmcost', url: import.meta.url })
