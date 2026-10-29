import { ApiError, postStructured } from '@shared/api'
export { ApiError }
const BASE = '/api/pii'

export interface ScanResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}


export async function scan(body: {
  sql?: string
  dir?: string
  dialect: string
  lang: string
}): Promise<ScanResponse> {
  return postStructured(`${BASE}/scan`, { ...body, report: true }, 'scan')
}

export interface MaskResponse {
  result: { counts: Record<string, number> } & Record<string, unknown>
  sql: string
  elapsed_ms: number
}

export async function mask(body: {
  sql?: string
  dir?: string
  dialect: string
  min_confidence: string
}): Promise<MaskResponse> {
  return postStructured(`${BASE}/mask`, body, 'mask')
}
