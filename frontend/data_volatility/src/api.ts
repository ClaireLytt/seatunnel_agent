import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/datavolatility'

export interface AnalyzeResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAnalyze(
  seriesText: string,
  lang: string,
  llm = false,
): Promise<AnalyzeResponse> {
  const body: Record<string, unknown> = { series_text: seriesText, lang, report: true }
  if (llm) body.llm = true
  return postStructured(`${BASE}/analyze`, body, 'analyze')
}
