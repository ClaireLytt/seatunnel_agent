// REST client for /api/llmcost (seatunnel_agent.agents.ai.llm_cost.api).

const BASE = '/api/llmcost'

export interface SummaryTotal {
  calls: number
  input: number
  output: number
  cost_usd: number
  unpriced_calls: number
}

export interface Summary {
  days: number
  total: SummaryTotal
  by_model: Record<string, { calls: number; input: number; output: number; cost_usd: number }>
  by_agent: Record<string, { calls: number; cost_usd: number }>
  by_day: Record<string, number>
  by_day_model: Record<string, Record<string, number>>
  unpriced_models: string[]
  anomalies: string[]
}

export interface SummaryResponse {
  summary: Summary
  report: string | null
  over_budget: boolean | null
  elapsed_ms: number
}

// 400 (malformed pricing override) carries the error text in FastAPI's
// `detail`; the page shows it in the report area.
export async function fetchSummary(
  days: number,
  budget: number | null,
  lang: string,
): Promise<SummaryResponse> {
  const params = new URLSearchParams({ days: String(days), lang, report: 'true' })
  if (budget !== null && budget > 0) params.set('budget', String(budget))
  const r = await fetch(`${BASE}/summary?${params}`)
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
    throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${r.status}`)
  }
  return r.json()
}

// ── Reserved for ticket 03 (price table / charts / CSV) ──────────────────────

export interface PriceEntry {
  prefix: string
  input_usd: number
  output_usd: number
  source: string
}

export interface PricesResponse {
  prices: PriceEntry[]
  override_path: string
}

export async function fetchPrices(): Promise<PricesResponse> {
  const r = await fetch(`${BASE}/prices`)
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
    throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${r.status}`)
  }
  return r.json()
}
