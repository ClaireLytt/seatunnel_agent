import { postSSE } from '@shared/sse'

export interface AgentMeta {
  key: string
  label_en: string
  label_zh: string
}

export interface Meta {
  suites: string[]
  agents: AgentMeta[]
}

export interface RunCounts {
  [verdict: string]: number
}

export type RunEvent =
  | { type: 'progress'; line: string }
  | { type: 'error'; message: string }
  | { type: 'done'; run_id: string; counts: RunCounts; elapsed_ms: number }

export interface RunEntry {
  run_id: string
  suite: string
  elapsed_ms: number
  counts: RunCounts
  has_report: boolean
}

const BASE = '/api/uitest'

export async function fetchRuns(): Promise<RunEntry[]> {
  const r = await fetch(`${BASE}/runs`)
  if (!r.ok) throw new Error(`runs: HTTP ${r.status}`)
  return (await r.json()).runs
}

export async function fetchMeta(): Promise<Meta> {
  const r = await fetch(`${BASE}/meta`)
  if (!r.ok) throw new Error(`meta: HTTP ${r.status}`)
  return r.json()
}

export async function runSuite(
  body: { suite: string; agent: string; case_ids: string; no_llm: boolean },
  onEvent: (e: RunEvent) => void,
): Promise<void> {
  await postSSE<RunEvent>(`${BASE}/run`, body, onEvent)
}

export async function saveCase(text: string): Promise<{ ids: string[]; path: string }> {
  const r = await fetch(`${BASE}/case`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
    throw new Error(data.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

export const reportUrl = (runId: string) => `${BASE}/report/${runId}`
export const reportDownloadUrl = (runId: string) => `${BASE}/report/${runId}/download`
