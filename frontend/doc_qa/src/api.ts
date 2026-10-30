// REST client for /api/docqa (seatunnel_agent.agents.ai.doc_qa.api).

import { fetchJson } from '@shared/api'

const BASE = '/api/docqa'

export interface AskResponse {
  markdown: string
  hits: Record<string, unknown>[]
  elapsed_ms: number
}

// Errors surface as ApiError{status, detail}; the page shows detail.
// `k` is not sent — the endpoint default (4) matches the old Gradio page.
export function ask(question: string, llm: boolean, lang: string): Promise<AskResponse> {
  return fetchJson(`${BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, llm, lang }),
  })
}
