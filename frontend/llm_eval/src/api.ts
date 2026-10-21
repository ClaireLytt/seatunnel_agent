// REST client for /api/llmeval (seatunnel_agent.agents.ai.llm_eval.api).

const BASE = '/api/llmeval'

export interface RunResponse {
  result: Record<string, unknown>
  regression: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

// 400 (suite parse error) and 503 (LLM not configured) carry the error
// text in FastAPI's `detail`; the page shows it in the report area.
export async function runSuite(
  suiteYaml: string,
  judge: boolean,
  lang: string,
): Promise<RunResponse> {
  const r = await fetch(`${BASE}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suite_yaml: suiteYaml, judge, lang, report: true }),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
    throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${r.status}`)
  }
  return r.json()
}

// ── Reserved for ticket 03 (validate / demo / history) ───────────────────────

export type ValidateResponse =
  | { ok: true; cases: number; agents: string[] }
  | { ok: false; error: string }

export async function validateSuite(suiteYaml: string): Promise<ValidateResponse> {
  const r = await fetch(`${BASE}/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suite_yaml: suiteYaml }),
  })
  if (!r.ok) throw new Error(`validate: HTTP ${r.status}`)
  return r.json()
}

export async function fetchDemoSuite(): Promise<string> {
  const r = await fetch(`${BASE}/demo`)
  if (!r.ok) throw new Error(`demo: HTTP ${r.status}`)
  return (await r.json()).text
}

export interface HistoryRun {
  ts: string
  suite: string
  score: number
  [k: string]: unknown
}

export async function fetchHistory(n = 50): Promise<HistoryRun[]> {
  const r = await fetch(`${BASE}/history?n=${n}`)
  if (!r.ok) throw new Error(`history: HTTP ${r.status}`)
  return (await r.json()).runs
}
