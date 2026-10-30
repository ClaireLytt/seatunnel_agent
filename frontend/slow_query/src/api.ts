import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/slowquery'

export interface DiagnoseResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runDiagnose(
  metrics: string,
  baselineFile: string | null,
  baselineText: string,
  lang: string,
): Promise<DiagnoseResponse> {
  const body: Record<string, unknown> = { metrics, lang, report: true }
  if (baselineFile) body.baseline_file = baselineFile
  if (baselineText.trim()) body.baseline_text = baselineText
  return postStructured(`${BASE}/diagnose`, body, 'diagnose')
}
