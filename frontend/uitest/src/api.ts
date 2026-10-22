import { fetchJson } from '@shared/api'
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
  return (await fetchJson<{ runs: RunEntry[] }>(`${BASE}/runs`)).runs
}

export function fetchMeta(): Promise<Meta> {
  return fetchJson(`${BASE}/meta`)
}

export async function runSuite(
  body: { suite: string; agent: string; case_ids: string; no_llm: boolean },
  onEvent: (e: RunEvent) => void,
): Promise<void> {
  try {
    await postSSE<RunEvent>(`${BASE}/run`, body, onEvent)
  } catch (e) {
    throw new Error(`run: ${e instanceof Error ? e.message : e}`)
  }
}

export function saveCase(text: string): Promise<{ ids: string[]; path: string }> {
  return fetchJson(`${BASE}/case`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
}

export const reportUrl = (runId: string) => `${BASE}/report/${runId}`
export const reportDownloadUrl = (runId: string) => `${BASE}/report/${runId}/download`
