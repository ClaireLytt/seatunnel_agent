// REST client for /api/triage (seatunnel_agent.agents.ai.issue_triage.api).

import { fetchJson } from '@shared/api'

const BASE = '/api/triage'

export interface TriageResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

// Errors surface as ApiError{status, detail} (503 = no key, 502 = engine
// failure); the page shows ⚠️ detail. `issues` is not sent — the endpoint
// then loads the bundled demo history, like the old Gradio page.
export function runTriage(title: string, body: string, lang: string): Promise<TriageResponse> {
  return fetchJson(`${BASE}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, body, lang, report: true }),
  })
}
