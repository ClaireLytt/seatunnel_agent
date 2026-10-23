import { ApiError, fetchJson, postStructured } from '@shared/api'
export { ApiError }
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


async function post<T>(path: string, body: Record<string, unknown>): Promise<T> {
  return postStructured(`${BASE}${path}`, body, path)
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
    report: true,
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
  return (await fetchJson<{ dialects: string[] }>(`${BASE}/dialects`)).dialects
}
