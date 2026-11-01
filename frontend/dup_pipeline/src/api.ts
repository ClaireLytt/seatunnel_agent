import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/duppipeline'

export interface DetectResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runDetect(
  sqlText: string,
  fanout: number,
  lang: string,
  llm = false,
): Promise<DetectResponse> {
  const body: Record<string, unknown> = {
    sql_text: sqlText,
    fanout,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/detect`, body, 'detect')
}
