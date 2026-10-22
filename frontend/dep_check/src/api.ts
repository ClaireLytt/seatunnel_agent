import { fetchJson } from '@shared/api'

const BASE = '/api/depcheck'

export interface CheckResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function checkText(
  pyprojectText: string,
  requirementsText: string,
  lang: string,
): Promise<CheckResponse> {
  return fetchJson(`${BASE}/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pyproject_text: pyprojectText,
      requirements_text: requirementsText,
      lang,
      report: true,
    }),
  })
}

export function checkSelf(lang: string): Promise<CheckResponse> {
  return fetchJson(`${BASE}/check-self?lang=${encodeURIComponent(lang)}`)
}
