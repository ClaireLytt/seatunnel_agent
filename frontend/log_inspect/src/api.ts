import { ApiError, postStructured } from '@shared/api'
export { ApiError }

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

function postScan(body: Record<string, unknown>): Promise<ScanResponse> {
  return postStructured(`${BASE}/scan`, body, 'scan')
}

export function scanDir(
  dir: string,
  includeWarn: boolean,
  top: number,
  lang: string,
): Promise<ScanResponse> {
  return postScan({ dir, include_warn: includeWarn, top, lang, report: true })
}

export function scanText(
  text: string,
  includeWarn: boolean,
  top: number,
  lang: string,
): Promise<ScanResponse> {
  return postScan({ text, include_warn: includeWarn, top, lang, report: true })
}

export function getAdvice(
  dir: string | null,
  text: string | null,
  includeWarn: boolean,
  top: number,
  lang: string,
): Promise<AdviceResponse> {
  const body: Record<string, unknown> = { include_warn: includeWarn, top, lang }
  if (dir) body.dir = dir
  if (text) body.text = text
  return postStructured(`${BASE}/advice`, body, 'advice')
}
