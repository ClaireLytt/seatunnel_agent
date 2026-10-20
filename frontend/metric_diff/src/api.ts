import { ApiError } from '@shared/api'
export { ApiError }
const BASE = '/api/metricdiff'

export interface CheckResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}


export async function checkMetrics(body: {
  sql_dir: string
  dialect: string
  lang: string
}): Promise<CheckResponse> {
  const r = await fetch(`${BASE}/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, report: true }),
  })
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as unknown)
      .catch(() => '')
    if (detail && typeof detail === 'object' && 'code' in (detail as object)) {
      const d = detail as { code: string; path?: string; error?: string }
      throw new ApiError(d.code, d.path ?? '', d.error ?? '')
    }
    throw new Error((detail as string) || `check: HTTP ${r.status}`)
  }
  return r.json()
}
