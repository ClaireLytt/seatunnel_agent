import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/capacityforecast'

export interface ForecastResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runForecast(
  seriesText: string,
  quota: number,
  lang: string,
  llm = false,
): Promise<ForecastResponse> {
  const body: Record<string, unknown> = {
    series_text: seriesText,
    quota,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/forecast`, body, 'forecast')
}
