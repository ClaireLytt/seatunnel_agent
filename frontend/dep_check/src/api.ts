const BASE = '/api/depcheck'

export interface CheckResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export async function checkText(
  pyprojectText: string,
  requirementsText: string,
  lang: string,
): Promise<CheckResponse> {
  const r = await fetch(`${BASE}/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pyproject_text: pyprojectText,
      requirements_text: requirementsText,
      lang,
      report: true,
    }),
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

export async function checkSelf(lang: string): Promise<CheckResponse> {
  const r = await fetch(`${BASE}/check-self?lang=${encodeURIComponent(lang)}`)
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as string)
      .catch(() => `HTTP ${r.status}`)
    throw new Error(detail)
  }
  return r.json()
}
