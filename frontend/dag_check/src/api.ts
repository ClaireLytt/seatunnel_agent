// Structured API error ({code: bad_dir|check_failed, …}) the UI localizes —
// shared legacy (code, path, error) constructor.
import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/dagcheck'

export interface CheckResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export async function checkDag(body: {
  sql_dir: string
  seatunnel_dir?: string
  dialect: string
  lang: string
}): Promise<CheckResponse> {
  return postStructured(`${BASE}/check`, { ...body, report: true }, 'check')
}
