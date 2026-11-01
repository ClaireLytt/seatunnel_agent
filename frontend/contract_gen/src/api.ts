import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/contractgen'

export interface GenResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runGenerate(
  sqlText: string,
  tables: string[],
  withTypes: boolean,
  strict: boolean,
  lang: string,
  llm = false,
): Promise<GenResponse> {
  const body: Record<string, unknown> = {
    sql_text: sqlText,
    tables,
    with_types: withTypes,
    allow_extra: !strict,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/generate`, body, 'generate')
}
