// REST client for /api/triage (seatunnel_agent.agents.ai.issue_triage.api).

const BASE = '/api/triage'

export interface TriageResponse {
  result: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

// Errors carry FastAPI's `detail` when present (503 = no key, 502 = engine
// failure); the page shows it as ⚠️ detail. `issues` is not sent — the
// endpoint then loads the bundled demo history, like the old Gradio page.
export async function runTriage(title: string, body: string, lang: string): Promise<TriageResponse> {
  const r = await fetch(`${BASE}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, body, lang, report: true }),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
    throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${r.status}`)
  }
  return r.json()
}
