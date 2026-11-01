import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/sqldiff'

export interface DiffResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runDiff(
  oldText: string,
  newText: string,
  lang: string,
  llm = false,
): Promise<DiffResponse> {
  const body: Record<string, unknown> = {
    old_text: oldText,
    new_text: newText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/diff`, body, 'diff')
}
