import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/fieldusage'

export interface AnalyzeResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAnalyze(
  ddlText: string,
  queriesText: string,
  lang: string,
  llm = false,
): Promise<AnalyzeResponse> {
  const body: Record<string, unknown> = {
    ddl_text: ddlText,
    queries_text: queriesText,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/analyze`, body, 'analyze')
}
