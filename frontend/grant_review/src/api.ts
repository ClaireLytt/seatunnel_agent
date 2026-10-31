import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/grantreview'

export interface ReviewResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runReview(
  applicationText: string,
  lang: string,
  llm = false,
): Promise<ReviewResponse> {
  const body: Record<string, unknown> = {
    application_text: applicationText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/review`, body, 'review')
}
