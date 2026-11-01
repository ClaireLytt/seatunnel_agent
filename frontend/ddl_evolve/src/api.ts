import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/ddlevolve'

export interface MigrateResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runMigrate(
  oldText: string,
  newText: string,
  dialect: string,
  lang: string,
  llm = false,
): Promise<MigrateResponse> {
  const body: Record<string, unknown> = {
    old_text: oldText,
    new_text: newText,
    dialect,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/migrate`, body, 'migrate')
}
