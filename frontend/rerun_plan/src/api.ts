import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/rerun'

export interface PlanResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runPlan(
  file: string | null,
  text: string | null,
  failed: string,
  succeeded: string,
  cmd: string,
  lang: string,
  llm = false,
): Promise<PlanResponse> {
  const body: Record<string, unknown> = { failed, lang, report: true }
  if (llm) body.llm = true
  if (file) body.file = file
  if (text) body.text = text
  if (succeeded.trim()) body.succeeded = succeeded.trim()
  if (cmd.trim()) body.cmd = cmd.trim()
  return postStructured(`${BASE}/plan`, body, 'plan')
}
