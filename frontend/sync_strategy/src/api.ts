import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/syncstrategy'

export interface RecommendResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runRecommend(
  file: string | null,
  text: string | null,
  lang: string,
  llm = false,
): Promise<RecommendResponse> {
  const body: Record<string, unknown> = { lang, report: true }
  if (llm) body.llm = true
  if (file) body.file = file
  if (text) body.text = text
  return postStructured(`${BASE}/recommend`, body, 'recommend')
}
