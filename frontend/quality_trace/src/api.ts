import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/qualitytrace'

export interface TraceResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runTrace(
  sqlText: string,
  table: string,
  column: string,
  symptom: string,
  lang: string,
  llm = false,
): Promise<TraceResponse> {
  const body: Record<string, unknown> = { sql_text: sqlText, table, lang, report: true }
  if (column.trim()) body.column = column.trim()
  if (symptom.trim()) body.symptom = symptom.trim()
  if (llm) body.llm = true
  return postStructured(`${BASE}/trace`, body, 'trace')
}
