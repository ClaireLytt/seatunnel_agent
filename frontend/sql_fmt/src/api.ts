import { ApiError, postStructured } from '@shared/api'
export { ApiError }
const BASE = '/api/sqlfmt'

export interface FormatResponse {
  result: Record<string, unknown> | null
  results: Record<string, unknown>[] | null
  report: string | null
  elapsed_ms: number
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
  return postStructured(`${BASE}/format`, body, 'format')
}
