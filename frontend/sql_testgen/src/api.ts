const BASE = '/api/testgen'

export interface GenerateResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export async function generateData(body: {
  sql: string
  ddl: string
  rows: number
  dialect: string
  validate_sqlite: boolean
  lang: string
}): Promise<GenerateResponse> {
  const r = await fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, report: true }),
  })
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as unknown)
      .catch(() => '')
    throw new Error((detail as string) || `generate: HTTP ${r.status}`)
  }
  return r.json()
}
