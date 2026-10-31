import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/joinaudit'

export interface AuditResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAudit(
  leftText: string,
  rightText: string,
  keys: string,
  lang: string,
  llm = false,
): Promise<AuditResponse> {
  const body: Record<string, unknown> = {
    left_text: leftText,
    right_text: rightText,
    keys,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/audit`, body, 'audit')
}
