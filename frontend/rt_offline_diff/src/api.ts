import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/rtoffline'

export interface CompareResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runCompare(
  realtimeText: string,
  offlineText: string,
  keys: string,
  tolerancePct: number,
  lang: string,
  llm = false,
): Promise<CompareResponse> {
  const body: Record<string, unknown> = {
    realtime_text: realtimeText,
    offline_text: offlineText,
    keys,
    tolerance_pct: tolerancePct,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/compare`, body, 'compare')
}
