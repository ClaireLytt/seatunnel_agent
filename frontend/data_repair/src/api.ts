import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/datarepair'

export interface PlanResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runPlan(
  dataText: string,
  table: string,
  pk: string,
  bizKey: string,
  lang: string,
  llm = false,
): Promise<PlanResponse> {
  const body: Record<string, unknown> = { data_text: dataText, lang, report: true }
  if (table.trim()) body.table = table.trim()
  if (pk.trim()) body.pk = pk.trim()
  if (bizKey.trim()) body.biz_key = bizKey.trim()
  if (llm) body.llm = true
  return postStructured(`${BASE}/plan`, body, 'plan')
}
