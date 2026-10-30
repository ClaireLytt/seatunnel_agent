import { ApiError, postStructured } from '@shared/api'
export { ApiError }
const BASE = '/api/schemadrift'

export interface DriftResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export async function diff(body: {
  old_sql?: string
  new_sql?: string
  old_path?: string
  new_path?: string
  dialect: string
  lang: string
}): Promise<DriftResponse> {
  return postStructured(`${BASE}/diff`, { ...body, report: true }, 'diff')
}
