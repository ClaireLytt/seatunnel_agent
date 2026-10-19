const BASE = '/api/sqlfmt'

export interface FormatResponse {
  result: Record<string, unknown> | null
  results: Record<string, unknown>[] | null
  report: string | null
  elapsed_ms: number
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

export async function formatSql(
  sql: string,
  dialect: string,
  lang: string,
): Promise<FormatResponse> {
  return postFormat({ sql, dialect, lang, report: true })
}

export async function checkDir(
  dir: string,
  dialect: string,
  lang: string,
): Promise<FormatResponse> {
  return postFormat({ dir, dialect, lang, report: true })
}

async function postFormat(body: Record<string, unknown>): Promise<FormatResponse> {
  const r = await fetch(`${BASE}/format`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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
    throw new Error((detail as string) || `format: HTTP ${r.status}`)
  }
  return r.json()
}
