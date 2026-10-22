// REST client for /api/ciinspect (seatunnel_agent.agents.devops.ci_inspect.api).

import { fetchJson } from '@shared/api'

const BASE = '/api/ciinspect'

export interface AnalyzeResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

// Errors surface as ApiError{status, detail}; the page shows the detail text.
export function analyze(body: {
  logs: { name: string; text: string }[]
  runs_json: string
  lang: string
}): Promise<AnalyzeResponse> {
  return fetchJson(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, report: true }),
  })
}
