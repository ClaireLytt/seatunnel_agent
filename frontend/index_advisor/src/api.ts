import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/indexadvisor'

export interface RecommendResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runRecommend(
  sqlDir: string | null,
  text: string | null,
  ddl: string,
  lang: string,
): Promise<RecommendResponse> {
  const body: Record<string, unknown> = { lang, report: true }
  if (sqlDir) body.sql_dir = sqlDir
  if (text) body.text = text
  if (ddl.trim()) body.ddl = ddl
  return postStructured(`${BASE}/recommend`, body, 'recommend')
}
