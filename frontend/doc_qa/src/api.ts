// REST client for /api/docqa (seatunnel_agent.agents.ai.doc_qa.api).

const BASE = '/api/docqa'

export interface AskResponse {
  markdown: string
  hits: Record<string, unknown>[]
  elapsed_ms: number
}

// Errors carry FastAPI's `detail` when present; the page shows it as ⚠️ detail.
// `k` is not sent — the endpoint default (4) matches the old Gradio page.
export async function ask(question: string, llm: boolean, lang: string): Promise<AskResponse> {
  const r = await fetch(`${BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, llm, lang }),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
    throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${r.status}`)
  }
  return r.json()
}
