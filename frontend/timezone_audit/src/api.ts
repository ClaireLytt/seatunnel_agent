import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/timezoneaudit'

export interface AuditResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAudit(dataText: string, lang: string, llm = false): Promise<AuditResponse> {
  const body: Record<string, unknown> = {
    data_text: dataText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/audit`, body, 'audit')
}
