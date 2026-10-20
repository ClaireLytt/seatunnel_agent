import { ApiError } from '@shared/api'
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
  const r = await fetch(`${BASE}/lint`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as unknown)
      .catch(() => '')
    if (detail && typeof detail === 'object' && 'code' in detail) {
      const d = detail as { code: string; path?: string }
      throw new ApiError(d.code, d.path ?? '')
    }
    throw new Error((detail as string) || `lint: HTTP ${r.status}`)
  }
  return r.json()
}
