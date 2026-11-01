import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/partitionhealth'

export interface CheckResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runCheck(listingText: string, lang: string, llm = false): Promise<CheckResponse> {
  const body: Record<string, unknown> = {
    listing_text: listingText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/check`, body, 'check')
}
