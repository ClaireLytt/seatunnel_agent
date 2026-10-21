const BASE = '/api/secretscan'

export interface ScanResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export async function scan(body: { text: string; lang: string }): Promise<ScanResponse> {
  const r = await fetch(`${BASE}/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, report: true }),
  })
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as unknown)
      .catch(() => '')
    throw new Error((typeof detail === 'string' && detail) || `scan: HTTP ${r.status}`)
  }
  return r.json()
}
