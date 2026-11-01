import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/metricattribution'

export interface AttributeResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAttribute(
  baselineText: string,
  currentText: string,
  dims: string,
  metric: string,
  lang: string,
  llm = false,
): Promise<AttributeResponse> {
  const body: Record<string, unknown> = {
    baseline_text: baselineText,
    current_text: currentText,
    dims,
    metric,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/attribute`, body, 'attribute')
}
