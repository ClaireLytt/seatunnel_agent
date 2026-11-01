import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/modelreview'

export interface ReviewResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runReview(
  sqlText: string,
  wideLimit: number,
  lang: string,
  llm = false,
): Promise<ReviewResponse> {
  const body: Record<string, unknown> = {
    sql_text: sqlText,
    wide_limit: wideLimit,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/review`, body, 'review')
}
