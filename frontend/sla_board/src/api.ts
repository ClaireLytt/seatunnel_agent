import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/slaboard'

export interface ScoreResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runScore(
  dataText: string,
  target: number,
  lang: string,
  llm = false,
): Promise<ScoreResponse> {
  const body: Record<string, unknown> = {
    data_text: dataText,
    target,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/score`, body, 'score')
}
