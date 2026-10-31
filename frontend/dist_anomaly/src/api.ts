import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/distanomaly'

export interface CompareResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runCompare(
  baselineText: string,
  currentText: string,
  maxRows: number,
  lang: string,
  llm = false,
): Promise<CompareResponse> {
  const body: Record<string, unknown> = {
    baseline_text: baselineText,
    current_text: currentText,
    max_rows: maxRows,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/compare`, body, 'compare')
}
