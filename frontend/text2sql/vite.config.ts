import { makeViteConfig } from '../shared/vite.base'

// Served at /text2sql (route swap #67); legacy Gradio at /text2sql-legacy.
export default makeViteConfig({ base: '/text2sql/', apiPath: '/api/text2sql', url: import.meta.url })
