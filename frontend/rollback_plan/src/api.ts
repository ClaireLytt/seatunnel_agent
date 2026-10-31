import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/rollbackplan'

export interface PlanResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runPlan(
  sqlText: string,
  table: string,
  partitions: string[],
  mode: string,
  snapshot: string,
  lang: string,
  llm = false,
): Promise<PlanResponse> {
  const body: Record<string, unknown> = {
    sql_text: sqlText,
    table,
    partitions,
    mode,
    lang,
    report: true,
  }
  if (snapshot.trim()) body.snapshot = snapshot.trim()
  if (llm) body.llm = true
  return postStructured(`${BASE}/plan`, body, 'plan')
}
