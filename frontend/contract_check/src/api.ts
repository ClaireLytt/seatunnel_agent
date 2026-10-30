import { ApiError, postStructured } from '@shared/api'
export { ApiError }
const BASE = '/api/contract'

export interface ContractResponse {
  result: {
    counts: Record<string, number>
  } & Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export async function scan(body: {
  sql?: string
  dir?: string
  contract: string
  dialect: string
  lang: string
}): Promise<ContractResponse> {
  return postStructured(`${BASE}/scan`, { ...body, report: true }, 'scan')
}
