import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/assetvalue'

export interface GradeResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runGrade(inventoryText: string, lang: string, llm = false): Promise<GradeResponse> {
  const body: Record<string, unknown> = {
    inventory_text: inventoryText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/grade`, body, 'grade')
}
