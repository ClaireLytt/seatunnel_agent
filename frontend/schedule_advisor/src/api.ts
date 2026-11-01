import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/scheduleadvisor'

export interface AdviseResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAdvise(planText: string, lang: string, llm = false): Promise<AdviseResponse> {
  const body: Record<string, unknown> = {
    plan_text: planText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/advise`, body, 'advise')
}
