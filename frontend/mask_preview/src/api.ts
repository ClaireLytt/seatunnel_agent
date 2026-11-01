import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/maskpreview'

export interface PreviewResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runPreview(
  dataText: string,
  previewRows: number,
  lang: string,
  llm = false,
): Promise<PreviewResponse> {
  const body: Record<string, unknown> = {
    data_text: dataText,
    preview_rows: previewRows,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/preview`, body, 'preview')
}
