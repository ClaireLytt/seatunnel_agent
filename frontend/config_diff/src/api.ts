import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/configdiff'

export interface DiffResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runDiff(
  leftText: string,
  rightText: string,
  lang: string,
  llm = false,
): Promise<DiffResponse> {
  const body: Record<string, unknown> = {
    left_text: leftText,
    right_text: rightText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/diff`, body, 'diff')
}
