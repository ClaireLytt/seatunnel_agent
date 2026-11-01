import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/storagecost'

export interface AnalyzeResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runAnalyze(
  inventoryText: string,
  partitionsText: string,
  retentionDays: number,
  lang: string,
  llm = false,
): Promise<AnalyzeResponse> {
  const body: Record<string, unknown> = {
    inventory_text: inventoryText,
    retention_days: retentionDays,
    lang,
    report: true,
  }
  if (partitionsText.trim()) body.partitions_text = partitionsText
  if (llm) body.llm = true
  return postStructured(`${BASE}/analyze`, body, 'analyze')
}
