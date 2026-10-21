import { ApiError, fetchJson } from '@shared/api'
export { ApiError }
const BASE = '/api/config_migrate'

export interface MigrateResponse {
  ok: boolean
  source_kind: string
  conf: string
  report: string
}

export interface BatchResponse {
  report: string
}


export function migrateText(text: string, lang: string): Promise<MigrateResponse> {
  return fetchJson(`${BASE}/migrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, lang }),
  })
}

export async function migrateBatch(
  jobsDir: string,
  outDir: string,
  lang: string,
): Promise<BatchResponse> {
  const r = await fetch(`${BASE}/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jobs_dir: jobsDir, out_dir: outDir, lang }),
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
    throw new Error((detail as string) || `batch: HTTP ${r.status}`)
  }
  return r.json()
}
