import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /docqa (see seatunnel_agent.agents.ai.doc_qa.api)
export default makeViteConfig({ base: '/docqa/', apiPath: '/api/docqa', url: import.meta.url })
