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

const BASE = '/api/uitest'

export async function fetchMeta(): Promise<Meta> {
  const r = await fetch(`${BASE}/meta`)
  if (!r.ok) throw new Error(`meta: HTTP ${r.status}`)
  return r.json()
}

export async function runSuite(
  body: { suite: string; agent: string; case_ids: string; no_llm: boolean },
  onEvent: (e: RunEvent) => void,
): Promise<void> {
  const r = await fetch(`${BASE}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok || !r.body) {
    const detail = await r.text().catch(() => '')
    throw new Error(`run: HTTP ${r.status} ${detail}`)
  }
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      for (const line of chunk.split('\n')) {
        if (line.startsWith('data: ')) onEvent(JSON.parse(line.slice(6)) as RunEvent)
      }
    }
  }
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
