import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/alertstorm'

export interface DigestResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runDigest(exportText: string, lang: string, llm = false): Promise<DigestResponse> {
  const body: Record<string, unknown> = {
    export_text: exportText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/digest`, body, 'digest')
}
