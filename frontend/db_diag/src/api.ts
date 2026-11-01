import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/dbdiag'

export interface DiagnoseResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runDiagnose(
  snapshotText: string,
  lang: string,
  llm = false,
): Promise<DiagnoseResponse> {
  const body: Record<string, unknown> = {
    snapshot_text: snapshotText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/diagnose`, body, 'diagnose')
}
