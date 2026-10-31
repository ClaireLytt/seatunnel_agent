import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/taskfailure'

export interface ClassifyResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runClassify(
  exportText: string,
  lang: string,
  llm = false,
): Promise<ClassifyResponse> {
  const body: Record<string, unknown> = {
    export_text: exportText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/classify`, body, 'classify')
}
