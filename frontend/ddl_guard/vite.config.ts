import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /ddlguard (see agents.data.ddl_guard.api)
export default makeViteConfig({ base: '/ddlguard/', apiPath: '/api/ddlguard', url: import.meta.url })
