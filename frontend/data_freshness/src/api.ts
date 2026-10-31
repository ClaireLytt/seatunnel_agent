import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/freshness'

export interface ScanResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runScan(
  file: string | null,
  text: string | null,
  rulesFile: string,
  now: string,
  lang: string,
): Promise<ScanResponse> {
  const body: Record<string, unknown> = { lang, report: true }
  if (file) body.file = file
  if (text) body.text = text
  if (rulesFile.trim()) body.rules_file = rulesFile.trim()
  if (now.trim()) body.now = now.trim()
  return postStructured(`${BASE}/scan`, body, 'scan')
}
