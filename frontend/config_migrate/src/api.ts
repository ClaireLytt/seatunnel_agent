const BASE = '/api/config_migrate'

export interface MigrateResponse {
  ok: boolean
  source_kind: string
  conf: string
  report: string
}

export async function migrateText(text: string, lang: string): Promise<MigrateResponse> {
  const r = await fetch(`${BASE}/migrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, lang }),
  })
  if (!r.ok) throw new Error(`migrate: HTTP ${r.status}`)
  return r.json()
}
