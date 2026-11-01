import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/retention'

export interface AdviseResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAdvise(
  dataText: string,
  activeDays: number,
  lang: string,
  llm = false,
): Promise<AdviseResponse> {
  const body: Record<string, unknown> = {
    data_text: dataText,
    active_days: activeDays,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/advise`, body, 'advise')
}
