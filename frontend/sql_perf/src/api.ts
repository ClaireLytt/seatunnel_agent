import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/sqlperf'

export interface AnalyzeResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAnalyze(
  file: string | null,
  text: string | null,
  lang: string,
): Promise<AnalyzeResponse> {
  const body: Record<string, unknown> = { lang, report: true }
  if (file) body.file = file
  if (text) body.text = text
  return postStructured(`${BASE}/analyze`, body, 'analyze')
}
