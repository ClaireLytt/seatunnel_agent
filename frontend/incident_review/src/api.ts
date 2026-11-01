import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/incidentreview'

export interface ReviewResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runReview(dataText: string, lang: string, llm = false): Promise<ReviewResponse> {
  const body: Record<string, unknown> = {
    data_text: dataText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/review`, body, 'review')
}
