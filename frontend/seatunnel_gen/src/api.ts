import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/seatunnelgen'

export interface GenResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runGenerate(
  sqlText: string,
  source: string,
  sink: string,
  jobMode: string,
  lang: string,
  llm = false,
): Promise<GenResponse> {
  const body: Record<string, unknown> = {
    sql_text: sqlText,
    source,
    sink,
    lang,
    report: true,
  }
  if (jobMode.trim()) body.job_mode = jobMode.trim().toUpperCase()
  if (llm) body.llm = true
  return postStructured(`${BASE}/generate`, body, 'generate')
}
