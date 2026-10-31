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
  place = '',
): Promise<SimulateResponse> {
  const body: Record<string, unknown> = { lang, report: true }
  if (file) body.file = file
  if (text) body.text = text
  if (place.trim()) body.place = place.trim()
  return postStructured(`${BASE}/simulate`, body, 'simulate')
}
