import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/sampleprofile'

export interface ProfileResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runProfile(
  dataFile: string | null,
  dataText: string,
  maxRows: number,
  lang: string,
  llm = false,
): Promise<ProfileResponse> {
  const body: Record<string, unknown> = { lang, report: true, max_rows: maxRows }
  if (llm) body.llm = true
  if (dataFile) body.data_file = dataFile
  if (dataText.trim()) body.data_text = dataText
  return postStructured(`${BASE}/profile`, body, 'profile')
}
