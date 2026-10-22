// REST client for /api/secretscan (seatunnel_agent.agents.devops.secret_scan.api).

import { fetchJson } from '@shared/api'

const BASE = '/api/secretscan'

export interface ScanResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

// Errors surface as ApiError{status, detail}; the page shows the detail text.
export function scan(body: { text: string; lang: string }): Promise<ScanResponse> {
  return fetchJson(`${BASE}/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, report: true }),
  })
}
