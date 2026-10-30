import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/backfillsql'

export interface GenerateResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runGenerate(
  file: string | null,
  text: string | null,
  lang: string,
): Promise<GenerateResponse> {
  const body: Record<string, unknown> = { lang, report: true }
  if (file) body.file = file
  if (text) body.text = text
  return postStructured(`${BASE}/generate`, body, 'generate')
}

export interface SpecsResponse {
  result: Record<string, unknown>[]
  report: string
  elapsed_ms: number
}

export function runSpecs(plan: string, lang: string): Promise<SpecsResponse> {
  return postStructured(`${BASE}/specs`, { plan, lang }, 'specs')
}
