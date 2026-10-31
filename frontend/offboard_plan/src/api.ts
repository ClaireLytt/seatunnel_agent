import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/offboardplan'

export interface PlanResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runPlan(
  sqlText: string,
  table: string,
  graceDays: number,
  lang: string,
  llm = false,
): Promise<PlanResponse> {
  const body: Record<string, unknown> = {
    sql_text: sqlText,
    table,
    grace_days: graceDays,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/plan`, body, 'plan')
}
