import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/costalloc'

export interface AllocateResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAllocate(
  dataText: string,
  storagePrice: number,
  computePrice: number,
  lang: string,
  llm = false,
): Promise<AllocateResponse> {
  const body: Record<string, unknown> = {
    data_text: dataText,
    storage_price: storagePrice,
    compute_price: computePrice,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/allocate`, body, 'allocate')
}
