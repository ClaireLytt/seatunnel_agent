import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/avro2ddl'

export interface ConvertResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runConvert(
  schemaText: string,
  table: string,
  dialect: string,
  lang: string,
  llm = false,
): Promise<ConvertResponse> {
  const body: Record<string, unknown> = {
    schema_text: schemaText,
    dialect,
    lang,
    report: true,
  }
  if (table.trim()) body.table = table.trim()
  if (llm) body.llm = true
  return postStructured(`${BASE}/convert`, body, 'convert')
}
