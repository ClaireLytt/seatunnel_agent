import { ApiError, postStructured } from '@shared/api'
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
  return postStructured(`${BASE}/check`, { ...body, report: true }, 'check')
}
