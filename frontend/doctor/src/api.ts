const BASE = '/api/doctor'

export interface DiagnoseResponse {
  reply: string
  deterministic: boolean
  elapsed_ms: number
}

export async function diagnose(
  complaint: string,
  lang: string,
): Promise<DiagnoseResponse> {
  const r = await fetch(`${BASE}/diagnose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ complaint, lang }),
  })
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as string)
      .catch(() => `HTTP ${r.status}`)
    throw new Error(detail)
  }
  return r.json()
}

export async function checkup(lang: string): Promise<DiagnoseResponse> {
  const r = await fetch(`${BASE}/checkup?lang=${encodeURIComponent(lang)}`)
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as string)
      .catch(() => `HTTP ${r.status}`)
    throw new Error(detail)
  }
  return r.json()
}
