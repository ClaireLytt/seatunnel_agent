import { fetchJson } from '@shared/api'

const BASE = '/api/doctor'

export interface DiagnoseResponse {
  reply: string
  deterministic: boolean
  elapsed_ms: number
}

export function diagnose(
  complaint: string,
  lang: string,
): Promise<DiagnoseResponse> {
  return fetchJson(`${BASE}/diagnose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ complaint, lang }),
  })
}

export function checkup(lang: string): Promise<DiagnoseResponse> {
  return fetchJson(`${BASE}/checkup?lang=${encodeURIComponent(lang)}`)
}
