// REST client for /api/llmeval (seatunnel_agent.agents.ai.llm_eval.api).

import { fetchJson } from '@shared/api'

const BASE = '/api/llmeval'

export interface RunResponse {
  result: Record<string, unknown>
  regression: Record<string, unknown>
  report: string | null
  elapsed_ms: number
}

// 400 (suite parse error) and 503 (LLM not configured) carry the error
// text in FastAPI's `detail`; the page shows it in the report area.
export function runSuite(suiteYaml: string, judge: boolean, lang: string): Promise<RunResponse> {
  return fetchJson(`${BASE}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suite_yaml: suiteYaml, judge, lang, report: true }),
  })
}

// ── Reserved for ticket 03 (validate / demo / history) ───────────────────────

export type ValidateResponse =
  | { ok: true; cases: number; agents: string[] }
  | { ok: false; error: string }

export function validateSuite(suiteYaml: string): Promise<ValidateResponse> {
  return fetchJson(`${BASE}/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suite_yaml: suiteYaml }),
  })
}

export async function fetchDemoSuite(): Promise<string> {
  return (await fetchJson<{ text: string }>(`${BASE}/demo`)).text
}

export interface HistoryRun {
  ts: string
  suite: string
  score: number
  [k: string]: unknown
}

export async function fetchHistory(n = 50): Promise<HistoryRun[]> {
  return (await fetchJson<{ runs: HistoryRun[] }>(`${BASE}/history?n=${n}`)).runs
}
