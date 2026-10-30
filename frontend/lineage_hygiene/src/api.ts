import { ApiError, postStructured } from '@shared/api'
export { ApiError }
const BASE = '/api/hygiene'

export interface HygieneResponse {
  result: {
    counts: Record<string, number>
  } & Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export async function scan(body: {
  sql?: string
  dir?: string
  dialect: string
  lang: string
}): Promise<HygieneResponse> {
  return postStructured(`${BASE}/scan`, { ...body, report: true }, 'scan')
}
