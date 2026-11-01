import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/backfill'

export interface PlanResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runPlan(
  file: string | null,
  text: string | null,
  rulesFile: string,
  sqlDir: string,
  cmd: string,
  lang: string,
): Promise<PlanResponse> {
  const body: Record<string, unknown> = { lang, report: true }
  if (file) body.file = file
  if (text) body.text = text
  if (rulesFile.trim()) body.rules_file = rulesFile.trim()
  if (sqlDir.trim()) body.sql_dir = sqlDir.trim()
  if (cmd.trim()) body.cmd = cmd.trim()
  return postStructured(`${BASE}/plan`, body, 'plan')
}
