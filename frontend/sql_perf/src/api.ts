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
  llm = false,
  sql = '',
  before = '',
): Promise<AnalyzeResponse> {
  const body: Record<string, unknown> = { lang, report: true }
  if (file) body.file = file
  if (text) body.text = text
  if (before.trim()) body.before_text = before
  if (llm) {
    body.llm = true
    body.sql = sql
  }
  return postStructured(`${BASE}/analyze`, body, 'analyze')
}
