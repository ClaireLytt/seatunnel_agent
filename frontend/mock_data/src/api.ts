import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/mockdata'

export interface GenResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runGenerate(
  dataText: string,
  count: number,
  seed: number,
  lang: string,
  llm = false,
): Promise<GenResponse> {
  const body: Record<string, unknown> = {
    data_text: dataText,
    count,
    seed,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/generate`, body, 'generate')
}
