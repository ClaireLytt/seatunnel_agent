const BASE = '/api/dagcheck'

export interface CheckResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

/** Structured API error ({code: bad_dir|check_failed, …}) the UI localizes. */
export class ApiError extends Error {
  code: string
  path: string
  error: string
  constructor(code: string, path: string, error = '') {
    super(`${code}: ${path || error}`)
    this.code = code
    this.path = path
    this.error = error
  }
}

export async function checkDag(body: {
  sql_dir: string
  seatunnel_dir?: string
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
