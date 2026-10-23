import { ApiError, fetchJson, postStructured } from '@shared/api'
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
  return postStructured(`${BASE}/batch`, { jobs_dir: jobsDir, out_dir: outDir, lang }, 'batch')
}
