import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/daggen'

export interface GenResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runGenerate(
  sqlText: string,
  dagId: string,
  schedule: string,
  lang: string,
  llm = false,
): Promise<GenResponse> {
  const body: Record<string, unknown> = {
    sql_text: sqlText,
    dag_id: dagId,
    schedule,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/generate`, body, 'generate')
}
