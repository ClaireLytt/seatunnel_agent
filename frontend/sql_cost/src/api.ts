import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/sqlcost'

export interface EstimateResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runEstimate(
  sql: string,
  statsFile: string | null,
  statsText: string,
  lang: string,
  assume = '',
): Promise<EstimateResponse> {
  const body: Record<string, unknown> = { sql, lang, report: true }
  if (statsFile) body.stats_file = statsFile
  if (statsText.trim()) body.stats_text = statsText
  const specs = assume
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean)
  if (specs.length) body.assume_partitions = specs
  return postStructured(`${BASE}/estimate`, body, 'estimate')
}
