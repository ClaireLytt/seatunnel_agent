import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/pipedoctor'

export interface DiagnoseResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export interface AdviceResponse {
  advice: string
  elapsed_ms: number
}

function postDiagnose(body: Record<string, unknown>): Promise<DiagnoseResponse> {
  return postStructured(`${BASE}/diagnose`, body, 'diagnose')
}

export function diagnoseDir(dir: string, top: number, lang: string): Promise<DiagnoseResponse> {
  return postDiagnose({ dir, top, lang, report: true })
}

export function diagnoseText(text: string, top: number, lang: string): Promise<DiagnoseResponse> {
  return postDiagnose({ text, top, lang, report: true })
}

export function runDiff(
  dir: string | null,
  text: string | null,
  baselineDir: string | null,
  baselineText: string | null,
  top: number,
  lang: string,
): Promise<DiagnoseResponse> {
  const body: Record<string, unknown> = { top, lang, report: true }
  if (dir) body.dir = dir
  if (text) body.text = text
  if (baselineDir) body.baseline_dir = baselineDir
  if (baselineText) body.baseline_text = baselineText
  return postStructured(`${BASE}/rundiff`, body, 'rundiff')
}

export function getAdvice(
  dir: string | null,
  text: string | null,
  top: number,
  lang: string,
): Promise<AdviceResponse> {
  const body: Record<string, unknown> = { top, lang }
  if (dir) body.dir = dir
  if (text) body.text = text
  return postStructured(`${BASE}/advice`, body, 'advice')
}
