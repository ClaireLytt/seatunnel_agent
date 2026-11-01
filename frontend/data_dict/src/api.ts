import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/datadict'

export interface GenerateResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runGenerate(
  catalogText: string,
  sqlText: string,
  lang: string,
  llm = false,
): Promise<GenerateResponse> {
  const body: Record<string, unknown> = {
    catalog_text: catalogText,
    lang,
    report: true,
  }
  if (sqlText.trim()) body.sql_text = sqlText
  if (llm) body.llm = true
  return postStructured(`${BASE}/generate`, body, 'generate')
}
