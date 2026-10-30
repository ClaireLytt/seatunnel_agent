import { ApiError, postStructured } from '@shared/api'
export { ApiError }
const BASE = '/api/metaquality'

export interface MetaQualityResponse {
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
}): Promise<MetaQualityResponse> {
  return postStructured(`${BASE}/scan`, { ...body, report: true }, 'scan')
}
