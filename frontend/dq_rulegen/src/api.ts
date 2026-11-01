import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/dqrulegen'

export interface GenResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runGenerate(
  dataText: string,
  table: string,
  where: string,
  lang: string,
  llm = false,
): Promise<GenResponse> {
  const body: Record<string, unknown> = {
    data_text: dataText,
    table,
    lang,
    report: true,
  }
  if (where.trim()) body.where = where.trim()
  if (llm) body.llm = true
  return postStructured(`${BASE}/generate`, body, 'generate')
}
