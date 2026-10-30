import { ApiError, postStructured } from '@shared/api'
export { ApiError }
const BASE = '/api/ddlguard'

export interface DdlGuardResponse {
  result: {
    counts: Record<string, number>
    undo_sql: string
  } & Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export async function scan(body: {
  sql?: string
  dir?: string
  dialect: string
  lang: string
}): Promise<DdlGuardResponse> {
  return postStructured(`${BASE}/scan`, { ...body, report: true }, 'scan')
}
