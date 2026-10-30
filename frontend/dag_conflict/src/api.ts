import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/dagconflict'

export interface SimulateResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runSimulate(
  file: string | null,
  text: string | null,
  lang: string,
): Promise<SimulateResponse> {
  const body: Record<string, unknown> = { lang, report: true }
  if (file) body.file = file
  if (text) body.text = text
  return postStructured(`${BASE}/simulate`, body, 'simulate')
}
