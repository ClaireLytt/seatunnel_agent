import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/schemaalign'

export interface AlignResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAlign(
  sourceText: string,
  sinkText: string,
  lang: string,
  llm = false,
): Promise<AlignResponse> {
  const body: Record<string, unknown> = {
    source_text: sourceText,
    sink_text: sinkText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/align`, body, 'align')
}
