import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/dupcheck'

export interface CheckResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runCheck(
  dataText: string,
  pk: string,
  bizKey: string,
  lang: string,
  llm = false,
): Promise<CheckResponse> {
  const body: Record<string, unknown> = { data_text: dataText, lang, report: true }
  if (pk.trim()) body.pk = pk.trim()
  if (bizKey.trim()) body.biz_key = bizKey.trim()
  if (llm) body.llm = true
  return postStructured(`${BASE}/check`, body, 'check')
}
