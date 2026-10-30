import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/dagopt'

export interface AnalyzeResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAnalyze(
  file: string | null,
  text: string | null,
  lang: string,
  deadline = 0,
): Promise<AnalyzeResponse> {
  const body: Record<string, unknown> = { lang, report: true }
  if (file) body.file = file
  if (text) body.text = text
  if (deadline > 0) body.deadline = deadline
  return postStructured(`${BASE}/analyze`, body, 'analyze')
}
