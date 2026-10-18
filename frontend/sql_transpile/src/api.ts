const BASE = '/api/transpile'

export interface TranslateResponse {
  output_sql: string
  report?: string
  stats: Record<string, unknown>
  statements: Record<string, unknown>[]
}

export interface BatchResponse {
  report?: string
  [k: string]: unknown
}

export interface AdviceResponse {
  status: 'ok' | 'none' | 'no_key' | 'error'
  advice: string | null
  detail?: string
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

async function post<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
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
    throw new Error((detail as string) || `${path}: HTTP ${r.status}`)
  }
  return r.json()
}

export function translateSql(
  sql: string,
  to: string,
  from: string,
  lang: string,
): Promise<TranslateResponse> {
  return post('/translate', {
    sql,
    to,
    ...(from !== 'auto' ? { from } : {}),
    lang,
    report: true,
  })
}

export function translateBatch(
  dir: string,
  outDir: string,
  to: string,
  from: string,
  lang: string,
): Promise<BatchResponse> {
  return post('/batch', {
    dir,
    ...(outDir ? { out_dir: outDir } : {}),
    to,
    ...(from !== 'auto' ? { from } : {}),
    lang,
  })
}

export function requestAdvice(
  sql: string,
  to: string,
  from: string,
  lang: string,
): Promise<AdviceResponse> {
  return post('/advice', {
    sql,
    to,
    ...(from !== 'auto' ? { from } : {}),
    lang,
  })
}

export async function fetchDialects(): Promise<string[]> {
  const r = await fetch(`${BASE}/dialects`)
  if (!r.ok) throw new Error(`dialects: HTTP ${r.status}`)
  return (await r.json()).dialects as string[]
}
