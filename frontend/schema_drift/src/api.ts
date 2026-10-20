import { ApiError } from '@shared/api'
export { ApiError }
const BASE = '/api/schemadrift'

export interface DriftResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}


export async function diff(body: {
  old_sql?: string
  new_sql?: string
  old_path?: string
  new_path?: string
  dialect: string
  lang: string
}): Promise<DriftResponse> {
  const r = await fetch(`${BASE}/diff`, {
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
    throw new Error((detail as string) || `diff: HTTP ${r.status}`)
  }
  return r.json()
}
