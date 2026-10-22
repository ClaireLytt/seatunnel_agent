const BASE = '/api/ciinspect'

export interface AnalyzeResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export async function analyze(body: {
  logs: { name: string; text: string }[]
  runs_json: string
  lang: string
}): Promise<AnalyzeResponse> {
  const r = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, report: true }),
  })
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as unknown)
      .catch(() => '')
    throw new Error((typeof detail === 'string' && detail) || `analyze: HTTP ${r.status}`)
  }
  return r.json()
}
