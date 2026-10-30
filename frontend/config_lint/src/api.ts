import { ApiError, postStructured } from '@shared/api'
export { ApiError }
const BASE = '/api/conflint'

export interface LintResponse {
  results: Record<string, unknown>[]
  report: string | null
  elapsed_ms: number
}

export async function lintConfig(config: string, lang: string): Promise<LintResponse> {
  return postLint({ config, lang, report: true })
}

export async function lintDir(dir: string, lang: string): Promise<LintResponse> {
  return postLint({ dir, lang, report: true })
}

async function postLint(body: Record<string, unknown>): Promise<LintResponse> {
  return postStructured(`${BASE}/lint`, body, 'lint')
}
