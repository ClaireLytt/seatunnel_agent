import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/pipemigrate'

export interface AssessResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAssess(
  dir: string | null,
  text: string | null,
  lang: string,
): Promise<AssessResponse> {
  const body: Record<string, unknown> = { lang, report: true }
  if (dir) body.dir = dir
  if (text) body.text = text
  return postStructured(`${BASE}/assess`, body, 'assess')
}
