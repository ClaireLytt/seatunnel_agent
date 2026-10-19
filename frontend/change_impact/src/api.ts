const BASE = '/api/lineage'

export interface ImpactResponse {
  report: string
  mermaid: string
  sql_diff?: string
  stats: Record<string, unknown>
  elapsed_ms: number
}

/** Structured API error ({code: bad_dir, path} guards, or plain detail). */
export class ApiError extends Error {
  code: string
  path: string
  error: string
  constructor(code: string, message: string, path = '', error = '') {
    super(message)
    this.code = code
    this.path = path
    this.error = error
  }
}

export async function analyzeImpact(body: {
  old_dir?: string
  new_dir?: string
  old_sql?: string
  new_sql?: string
  context_dir?: string
  depth: number
  sql_dialect: string
  lang: string
}): Promise<ImpactResponse> {
  const r = await fetch(`${BASE}/impact`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as unknown)
      .catch(() => '')
    if (detail && typeof detail === 'object' && 'code' in (detail as object)) {
      const d = detail as { code: string; message?: string; path?: string; error?: string }
      throw new ApiError(d.code, d.message ?? d.code, d.path ?? '', d.error ?? '')
    }
    throw new Error((detail as string) || `impact: HTTP ${r.status}`)
  }
  return r.json()
}
