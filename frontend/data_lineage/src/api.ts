const BASE = '/api/lineage'

/** Source params every endpoint accepts; session_id reuses the built graph. */
export interface SourceParams {
  session_id: string
  sql_dir?: string
  sql_dialect?: string
  seatunnel_dir?: string
  use_hive?: boolean
  meta_table?: string
  partition?: string
}

export interface BuildResponse {
  stats: { tables: number; edges: number; column_edges: number; sla_tables: number }
  tables: string[]
  warnings: string[]
}

export interface QueryResponse {
  report: string
  mermaid: string
  warnings: string[]
}

export interface PathResponse {
  found: boolean
  markdown: string
  mermaid: string
}

export interface SnapshotInfo {
  file: string
  name?: string
  saved_at?: string
}

export interface SseFrame {
  type: 'step' | 'tool' | 'delta' | 'final'
  [k: string]: unknown
}

/** Structured API error ({code} guards, or 404 {message, suggestions}). */
export class ApiError extends Error {
  code: string
  suggestions: string[]
  constructor(code: string, message: string, suggestions: string[] = []) {
    super(message)
    this.code = code
    this.suggestions = suggestions
  }
}

async function request<T>(path: string, body?: Record<string, unknown>): Promise<T> {
  const r = await fetch(`${BASE}${path}`, body === undefined ? undefined : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as unknown)
      .catch(() => '')
    if (detail && typeof detail === 'object') {
      const d = detail as { code?: string; message?: string; suggestions?: string[] }
      throw new ApiError(d.code ?? 'error', d.message ?? d.code ?? `${path}: HTTP ${r.status}`,
        d.suggestions ?? [])
    }
    throw new Error((detail as string) || `${path}: HTTP ${r.status}`)
  }
  return r.json()
}

let sessionPromise: Promise<string> | null = null

export function getSessionId(): Promise<string> {
  if (!sessionPromise) {
    sessionPromise = (async () => {
      const { session_id } = await request<{ session_id: string }>('/session', {})
      return session_id
    })()
  }
  return sessionPromise
}

export function build(src: SourceParams): Promise<BuildResponse> {
  return request('/build', { ...src })
}

export function query(
  src: SourceParams,
  table: string,
  direction: string,
  depth: number,
  column: string,
): Promise<QueryResponse> {
  return request('/query', {
    ...src,
    table,
    direction,
    depth,
    ...(column ? { column } : {}),
  })
}

export function search(src: SourceParams, keyword: string): Promise<{ matches: string[] }> {
  return request('/search', { ...src, keyword })
}

export function findPath(src: SourceParams, from: string, dst: string): Promise<PathResponse> {
  return request('/path', { ...src, src: from, dst })
}

export function slaImpact(
  src: SourceParams,
  table: string,
  delayHours: number,
  depth: number,
): Promise<{ markdown: string; mermaid: string }> {
  return request('/sla_impact', { ...src, table, delay_hours: delayHours, depth })
}

export function healthCheck(src: SourceParams): Promise<{ markdown: string }> {
  return request('/check', { ...src })
}

export function saveSnapshot(src: SourceParams, name: string): Promise<{ file: string }> {
  return request('/snapshot', { ...src, name })
}

export function snapshotDiff(src: SourceParams, snapshot: string): Promise<{ markdown: string }> {
  return request('/snapshot_diff', { ...src, snapshot })
}

export function listSnapshots(): Promise<{ snapshots: SnapshotInfo[] }> {
  return request('/snapshots')
}

/** SSE agent Q&A: calls onFrame per frame, resolves on the final frame. */
export async function analyzeStream(
  src: SourceParams,
  question: string,
  onFrame: (f: SseFrame) => void,
): Promise<void> {
  const r = await fetch(`${BASE}/analyze/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...src, question }),
  })
  if (!r.ok || !r.body) {
    const detail = await r
      .json()
      .then((d) => d.detail as unknown)
      .catch(() => '')
    if (detail && typeof detail === 'object' && 'code' in (detail as object)) {
      const d = detail as { code: string; message?: string }
      throw new ApiError(d.code, d.message ?? d.code)
    }
    throw new Error((detail as string) || `analyze: HTTP ${r.status}`)
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
      const raw = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      if (raw.startsWith('data: ')) {
        try {
          onFrame(JSON.parse(raw.slice(6)) as SseFrame)
        } catch {
          /* malformed frame — skip */
        }
      }
    }
  }
}
