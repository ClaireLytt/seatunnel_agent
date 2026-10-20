// REST client for /api/promptlab (seatunnel_agent.agents.ai.prompt_lab.api).

const BASE = '/api/promptlab'

export const ACTIVE = '(active)'

export interface Cell {
  profile: string
  provider: string
  model: string
  reply: string
  thinking: string
  input_tokens: number
  output_tokens: number
  latency_ms: number
  error: string | null
}

export interface RunResponse {
  cells: Cell[]
  report: string | null
  all_failed: boolean
  elapsed_ms: number
}

// 400 (ValueError) carries the error text in FastAPI's `detail`;
// the page shows it in the report area.
export async function runMatrix(
  prompt: string,
  system: string,
  profiles: string[],
  parallel: boolean,
  lang: string,
): Promise<RunResponse> {
  const r = await fetch(`${BASE}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      system: system || null,
      profiles,
      parallel,
      lang,
      report: true,
    }),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
    throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${r.status}`)
  }
  return r.json()
}

export async function fetchProfiles(): Promise<string[]> {
  const r = await fetch(`${BASE}/profiles`)
  if (!r.ok) throw new Error(`profiles: HTTP ${r.status}`)
  return (await r.json()).profiles
}

// ── Reserved for ticket 03 (diff / history) ──────────────────────────────────

export interface DiffCell {
  profile: string
  model?: string
  reply?: string
}

export async function diffCells(a: DiffCell, b: DiffCell, lang: string): Promise<string> {
  const r = await fetch(`${BASE}/diff`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ a, b, lang }),
  })
  if (!r.ok) throw new Error(`diff: HTTP ${r.status}`)
  return (await r.json()).markdown
}

export interface HistoryRun {
  ts: string
  prompt_preview: string
  cells: { profile?: string; error?: string | null }[]
  [k: string]: unknown
}

export async function fetchHistory(n = 20): Promise<HistoryRun[]> {
  const r = await fetch(`${BASE}/history?n=${n}`)
  if (!r.ok) throw new Error(`history: HTTP ${r.status}`)
  return (await r.json()).runs
}
