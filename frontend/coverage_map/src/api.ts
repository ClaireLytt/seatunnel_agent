import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/coveragemap'

export interface MapResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runMap(
  ddlText: string,
  rulesText: string,
  contractText: string,
  lang: string,
  llm = false,
): Promise<MapResponse> {
  const body: Record<string, unknown> = {
    ddl_text: ddlText,
    lang,
    report: true,
  }
  if (rulesText.trim()) body.rules_text = rulesText
  if (contractText.trim()) body.contract_text = contractText
  if (llm) body.llm = true
  return postStructured(`${BASE}/map`, body, 'map')
}
