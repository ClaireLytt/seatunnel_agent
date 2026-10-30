import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/slatrace'

export interface TraceResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runTrace(
  file: string | null,
  text: string | null,
  target: string,
  deadline: string,
  top: number,
  lang: string,
): Promise<TraceResponse> {
  const body: Record<string, unknown> = { target, top, lang, report: true }
  if (file) body.file = file
  if (text) body.text = text
  if (deadline.trim()) body.deadline = deadline.trim()
  return postStructured(`${BASE}/trace`, body, 'trace')
}
