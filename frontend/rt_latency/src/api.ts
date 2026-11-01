import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/rtlatency'

export interface AnalyzeResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAnalyze(
  eventsText: string,
  slaMs: number,
  lang: string,
  llm = false,
): Promise<AnalyzeResponse> {
  const body: Record<string, unknown> = {
    events_text: eventsText,
    sla_ms: slaMs,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/analyze`, body, 'analyze')
}
