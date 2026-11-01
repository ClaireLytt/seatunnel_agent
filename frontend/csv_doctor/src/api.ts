import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/csvdoctor'

export interface DiagnoseResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runDiagnose(
  dataText: string,
  lang: string,
  llm = false,
): Promise<DiagnoseResponse> {
  const body: Record<string, unknown> = {
    data_text: dataText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/diagnose`, body, 'diagnose')
}
