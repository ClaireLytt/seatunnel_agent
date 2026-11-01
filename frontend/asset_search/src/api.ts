import { ApiError, postStructured } from '@shared/api'
export { ApiError }

const BASE = '/api/assetsearch'

export interface SearchResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

export function runSearch(
  catalogText: string,
  query: string,
  lang: string,
  llm = false,
): Promise<SearchResponse> {
  const body: Record<string, unknown> = {
    catalog_text: catalogText,
    query,
    lang,
    report: true,
  }
  if (llm) body.llm = true
  return postStructured(`${BASE}/search`, body, 'search')
}
