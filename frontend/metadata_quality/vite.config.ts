import { makeViteConfig } from '../shared/vite.base'

// Served by FastAPI at /metaquality (see agents.data.metadata_quality.api)
export default makeViteConfig({ base: '/metaquality/', apiPath: '/api/metaquality', url: import.meta.url })
