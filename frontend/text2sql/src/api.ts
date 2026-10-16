const BASE = '/api/text2sql'

export type DsType = string

export interface Datasource {
  ds_type: DsType
  defaults: Partial<DbConfig>
}

export async function fetchDatasources(): Promise<Datasource[]> {
  const r = await fetch(`${BASE}/datasources`)
  if (!r.ok) throw new Error(`datasources: HTTP ${r.status}`)
  return (await r.json()).datasources
}

export interface DbConfig {
  host?: string
  port?: string
  database?: string
  username?: string
  password?: string
}

export interface SessionMeta {
  session_id: string
  ds_type: string
  table_count: number
  tables: string[]
}

export async function connect(dsType: DsType, dbConfig: DbConfig): Promise<SessionMeta> {
  const r = await fetch(`${BASE}/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ds_type: dsType, db_config: dbConfig }),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
    throw new Error(data.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

export type ChatEvent =
  | { type: 'text'; text: string }
  | { type: 'delta'; text: string }
  | { type: 'tool_call'; name: string }
  | {
      type: 'result'
      sql: string
      columns: string[]
      rows: unknown[][]
      row_count: number
      chart_type?: string | null
    }
  | { type: 'final'; text: string; stopped?: boolean }
  | { type: 'error'; message: string }

export async function chatStream(
  sessionId: string,
  question: string,
  onEvent: (e: ChatEvent) => void,
): Promise<void> {
  const { postSSE } = await import('@shared/sse')
  await postSSE<ChatEvent>(`${BASE}/chat`, { session_id: sessionId, question }, onEvent)
}

export async function stopChat(sessionId: string): Promise<void> {
  await fetch(`${BASE}/chat/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
}

export async function resetSession(sessionId: string): Promise<SessionMeta> {
  const r = await fetch(`${BASE}/session/${sessionId}/reset`, { method: 'POST' })
  if (!r.ok) throw new Error(`reset: HTTP ${r.status}`)
  return r.json()
}

export interface TableInfo {
  name: string
  column_count: number
  comment: string
}

export interface TableDetail {
  name: string
  comment: string
  columns: { name: string; type: string; comment: string }[]
  partition_columns: { name: string; type: string }[]
}

const j = async (r: Response) => {
  if (!r.ok) {
    const d = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
    throw new Error(d.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

export const fetchSchema = (sid: string): Promise<{ tables: TableInfo[] }> =>
  fetch(`${BASE}/session/${sid}/schema`).then(j)

export const fetchTable = (sid: string, name: string): Promise<TableDetail> =>
  fetch(`${BASE}/session/${sid}/schema/${encodeURIComponent(name)}`).then(j)

export const filterTables = (sid: string, tables: string[]): Promise<SessionMeta> =>
  fetch(`${BASE}/session/${sid}/schema/filter`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tables }),
  }).then(j)

export const reloadSchema = (sid: string): Promise<SessionMeta> =>
  fetch(`${BASE}/session/${sid}/schema/reload`, { method: 'POST' }).then(j)

export interface QlogRecord {
  timestamp: string
  user_query: string
  generated_sql: string
  status: string
  exec_time_ms?: number
  row_count?: number
}

export interface SavedSession {
  id: string
  title: string
  updated_at: string
  ds_type: string
}

export const fetchQlog = (n = 100): Promise<{ records: QlogRecord[] }> =>
  fetch(`${BASE}/history/qlog?n=${n}`).then(j)

export const deleteQlog = (indices: number[]): Promise<{ deleted: number }> =>
  fetch(`${BASE}/history/qlog/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ indices }),
  }).then(j)

export const clearQlog = (): Promise<{ cleared: boolean }> =>
  fetch(`${BASE}/history/qlog/clear`, { method: 'POST' }).then(j)

export const qlogExportUrl = `${BASE}/history/qlog/export`

export const fetchSavedSessions = (): Promise<{ sessions: SavedSession[] }> =>
  fetch(`${BASE}/history/sessions`).then(j)

export const resumeSaved = (
  sid: string,
  savedId: string,
): Promise<{ title: string; chat: { role: string; content: string }[] }> =>
  fetch(`${BASE}/session/${sid}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ saved_id: savedId }),
  }).then(j)
