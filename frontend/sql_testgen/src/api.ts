import { fetchJson } from '@shared/api'

const BASE = '/api/testgen'

export interface GenerateResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function generateData(body: {
  sql: string
  ddl: string
  rows: number
  dialect: string
  validate_sqlite: boolean
  lang: string
}): Promise<GenerateResponse> {
  return fetchJson(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, report: true }),
  })
}
