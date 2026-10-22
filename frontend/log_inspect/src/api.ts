const BASE = '/api/loginspect'

export interface ScanResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export interface AdviceResponse {
  advice: string
  elapsed_ms: number
}

export async function scanDir(
  dir: string,
  includeWarn: boolean,
  top: number,
  lang: string,
): Promise<ScanResponse> {
  return postScan({ dir, include_warn: includeWarn, top, lang, report: true })
}

export async function scanText(
  text: string,
  includeWarn: boolean,
  top: number,
  lang: string,
): Promise<ScanResponse> {
  return postScan({ text, include_warn: includeWarn, top, lang, report: true })
}

async function postScan(body: Record<string, unknown>): Promise<ScanResponse> {
  const r = await fetch(`${BASE}/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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

export async function getAdvice(
  dir: string | null,
  text: string | null,
  includeWarn: boolean,
  top: number,
  lang: string,
): Promise<AdviceResponse> {
  const body: Record<string, unknown> = { include_warn: includeWarn, top, lang }
  if (dir) body.dir = dir
  if (text) body.text = text
  const r = await fetch(`${BASE}/advice`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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
