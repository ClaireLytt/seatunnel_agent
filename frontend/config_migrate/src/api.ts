const BASE = '/api/config_migrate'

export interface MigrateResponse {
  ok: boolean
  source_kind: string
  conf: string
  report: string
}

export interface BatchResponse {
  report: string
}

/** Structured API error (e.g. {code: 'bad_dir', path}) the UI can localize. */
export class ApiError extends Error {
  code: string
  path: string
  constructor(code: string, path: string) {
    super(`${code}: ${path}`)
    this.code = code
    this.path = path
  }
}

export async function migrateText(text: string, lang: string): Promise<MigrateResponse> {
  const r = await fetch(`${BASE}/migrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, lang }),
  })
  if (!r.ok) throw new Error(`migrate: HTTP ${r.status}`)
  return r.json()
}

export async function migrateBatch(
  jobsDir: string,
  outDir: string,
  lang: string,
): Promise<BatchResponse> {
  const r = await fetch(`${BASE}/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jobs_dir: jobsDir, out_dir: outDir, lang }),
  })
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as unknown)
      .catch(() => '')
    if (detail && typeof detail === 'object' && 'code' in detail) {
      const d = detail as { code: string; path?: string }
      throw new ApiError(d.code, d.path ?? '')
    }
    throw new Error((detail as string) || `batch: HTTP ${r.status}`)
  }
  return r.json()
}
