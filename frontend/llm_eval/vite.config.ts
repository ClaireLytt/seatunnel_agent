import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /llmeval (see seatunnel_agent.agents.ai.llm_eval.api)
export default makeViteConfig({ base: '/llmeval/', apiPath: '/api/llmeval', url: import.meta.url })
