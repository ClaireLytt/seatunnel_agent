import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/layercheck'

export interface CheckResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runCheck(
  sqlText: string,
  layersText: string,
  lang: string,
  llm = false,
): Promise<CheckResponse> {
  const body: Record<string, unknown> = { sql_text: sqlText, lang, report: true }
  if (layersText.trim()) body.layers_text = layersText
  if (llm) body.llm = true
  return postStructured(`${BASE}/check`, body, 'check')
}
