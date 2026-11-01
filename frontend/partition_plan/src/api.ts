import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/partitionplan'

export interface PlanResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runPlan(
  dataText: string,
  queriesText: string,
  lang: string,
  llm = false,
): Promise<PlanResponse> {
  const body: Record<string, unknown> = {
    data_text: dataText,
    queries_text: queriesText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/plan`, body, 'plan')
}
