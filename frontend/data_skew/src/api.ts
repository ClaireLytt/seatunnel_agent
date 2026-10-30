const BASE = '/api/skew'

export interface AnalyzeResponse {
  report: string
  optimized_sql: string
  llm_unavailable: boolean
  elapsed_ms: number
}

export interface SectionResponse {
  report: string
  status: string
  patched_conf?: string | null
}

export interface HistoryRecord {
  timestamp?: string
  source?: string
  dialect?: string
  mode?: string
  sql?: string
  counts?: { high?: number; medium?: number; low?: number }
  [k: string]: unknown
}

export interface PresetSummary {
  name: string
  ds_type: string
  supported: boolean
}

export interface PresetDetail {
  name: string
  ds_type: string
  host: string
  port: string
  database: string
  username: string
  password: string
}

/** Structured API error: guards come back as {code, message} with the
 * message already localized by the backend dsk() dict. */
export class ApiError extends Error {
  code: string
  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init)
  if (!r.ok) {
    const detail = await r
      .json()
      .then((d) => d.detail as unknown)
      .catch(() => '')
    if (detail && typeof detail === 'object' && 'code' in detail) {
      const d = detail as { code: string; message?: string }
      throw new ApiError(d.code, d.message ?? d.code)
    }
    throw new Error((detail as string) || `${path}: HTTP ${r.status}`)
  }
  return r.json()
}

function post<T>(path: string, body: Record<string, unknown>): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

let sessionPromise: Promise<string> | null = null

/** Server session id for this tab (connection + probe cache live there). */
export function getSessionId(): Promise<string> {
  if (!sessionPromise) {
    sessionPromise = (async () => {
      try {
        const cached = sessionStorage.getItem('dsk-session-id')
        if (cached) {
          // validate: a restarted server forgets old ids
          const r = await fetch(`${BASE}/status?session_id=${cached}`)
          if (r.ok) return cached
        }
      } catch {
        /* sessionStorage unavailable — fall through to a fresh session */
      }
      const { session_id } = await post<{ session_id: string }>('/session', {})
      try {
        sessionStorage.setItem('dsk-session-id', session_id)
      } catch {
        /* ignore */
      }
      return session_id
    })()
  }
  return sessionPromise
}

export function analyze(body: {
  sql: string
  dialect: string
  mode: string
  sample: number
  lang: string
  session_id: string
}): Promise<AnalyzeResponse> {
  return post('/analyze', body)
}

export function connect(body: Record<string, unknown>): Promise<{ status: string }> {
  return post('/connect', body)
}

export function verify(body: Record<string, unknown>): Promise<SectionResponse> {
  return post('/verify', body)
}

export function consistency(body: Record<string, unknown>): Promise<SectionResponse> {
  return post('/consistency', body)
}

export function splitkey(body: Record<string, unknown>): Promise<SectionResponse> {
  return post('/splitkey', body)
}

export function runtimeHistoryServer(body: Record<string, unknown>): Promise<SectionResponse> {
  return post('/runtime/history-server', body)
}

export function runtimeFlink(body: Record<string, unknown>): Promise<SectionResponse> {
  return post('/runtime/flink', body)
}

export async function runtimeEventlog(
  file: File,
  report: string,
  lang: string,
  sessionId: string,
): Promise<SectionResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('report', report)
  form.append('lang', lang)
  form.append('session_id', sessionId)
  return request('/runtime/eventlog', { method: 'POST', body: form })
}

export interface DriftMetric {
  metric: string
  baseline: number
  current: number
  delta: number
}

export interface DriftItem {
  table: string
  column: string
  verdict: 'drift' | 'stable' | 'insufficient'
  samples: number
  drifts: DriftMetric[]
  hot_value?: { prev: string; cur: string; changed: boolean }
  text: string
}

export async function skewDrift(lang: string): Promise<DriftItem[]> {
  const data = await request<{ items: DriftItem[] }>(`/drift?lang=${encodeURIComponent(lang)}`)
  return data.items
}

export async function historyRecent(): Promise<HistoryRecord[]> {
  const data = await request<{ records: HistoryRecord[] }>('/history')
  return data.records
}

export function presetsList(): Promise<{ presets: PresetSummary[] }> {
  return request('/presets')
}

export function presetGet(name: string): Promise<PresetDetail> {
  return request(`/presets/${encodeURIComponent(name)}`)
}
