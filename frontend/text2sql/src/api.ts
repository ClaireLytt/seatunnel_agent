import { fetchJson } from '@shared/api'

const BASE = '/api/text2sql'

export type DsType = string

export interface Datasource {
  ds_type: DsType
  defaults: Partial<DbConfig>
}

export async function fetchDatasources(): Promise<Datasource[]> {
  const data = await fetchJson<{ datasources: Datasource[] }>(`${BASE}/datasources`)
  return data.datasources
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

export function connect(dsType: DsType, dbConfig: DbConfig): Promise<SessionMeta> {
  return fetchJson(`${BASE}/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ds_type: dsType, db_config: dbConfig }),
  })
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

export function resetSession(sessionId: string): Promise<SessionMeta> {
  return fetchJson(`${BASE}/session/${sessionId}/reset`, { method: 'POST' })
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

export const fetchSchema = (sid: string): Promise<{ tables: TableInfo[] }> =>
  fetchJson(`${BASE}/session/${sid}/schema`)

export const fetchTable = (sid: string, name: string): Promise<TableDetail> =>
  fetchJson(`${BASE}/session/${sid}/schema/${encodeURIComponent(name)}`)

export const filterTables = (sid: string, tables: string[]): Promise<SessionMeta> =>
  fetchJson(`${BASE}/session/${sid}/schema/filter`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tables }),
  })

export const reloadSchema = (sid: string): Promise<SessionMeta> =>
  fetchJson(`${BASE}/session/${sid}/schema/reload`, { method: 'POST' })

// ── Templates ───────────────────────────────────────────────────────

export interface Template {
  id: string
  name_en: string
  name_zh: string
  description_en: string
  description_zh: string
  pattern: string
}

export const fetchTemplates = (): Promise<{ templates: Template[] }> =>
  fetchJson(`${BASE}/templates`)

// ── Metrics catalog ─────────────────────────────────────────────────

export interface MetricInfo {
  name: string
  display_name: string
  aliases: string[]
  description: string
  type: string
  table: string
  expression: string
  numerator: string
  denominator: string
  time_column: string
  dimensions: string[]
  default_filters: string[]
  unit: string
  owner: string
}

export const fetchMetrics = (): Promise<{ count: number; metrics: MetricInfo[] }> =>
  fetchJson(`${BASE}/metrics`)

// ── Boards ──────────────────────────────────────────────────────────

export interface BoardItem {
  id: string
  title: string
  sql: string
  ds_type: string
  pinned_at: string
}

export interface Board {
  id: string
  name: string
  items: BoardItem[]
  created_at: string
}

export const fetchBoards = (): Promise<{ boards: Board[] }> =>
  fetchJson(`${BASE}/boards`)

export const createBoard = (name: string): Promise<{ board: Board }> =>
  fetchJson(`${BASE}/boards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })

export const deleteBoard = (id: string): Promise<{ deleted: boolean }> =>
  fetchJson(`${BASE}/boards/${id}`, { method: 'DELETE' })

export const pinToBoard = (
  boardId: string,
  title: string,
  sql: string,
  ds_type = '',
): Promise<{ item: BoardItem }> =>
  fetchJson(`${BASE}/boards/${boardId}/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, sql, ds_type }),
  })

export interface BoardRenderResult {
  id: string
  title: string
  sql: string
  columns?: string[]
  rows?: unknown[][]
  row_count?: number
  error?: string
}

export const renderBoard = (
  boardId: string,
  sessionId: string,
): Promise<{ results: BoardRenderResult[] }> =>
  fetchJson(`${BASE}/boards/${boardId}/render?session_id=${sessionId}`)

// ── Subscriptions ───────────────────────────────────────────────────

export interface Subscription {
  id: string
  name: string
  cron: string
  source_type: string
  metric: string
  metrics?: string[]
  favorite_id: string
  webhook_url: string
  enabled: boolean
  last_run_at: string
  last_status: string
  last_error: string
}

export const fetchSubscriptions = (): Promise<{ subscriptions: Subscription[] }> =>
  fetchJson(`${BASE}/subscriptions`)

export const createSubscription = (
  data: {
    name: string; cron: string; source_type: string; metric?: string
    favorite_id?: string; ds_type?: string; connection?: string
    database?: string; webhook_url?: string; lang?: string
    threshold_pct?: number; watch_mode?: string; max_lag_days?: number
    metrics?: string[]
  },
): Promise<{ subscription: Subscription }> =>
  fetchJson(`${BASE}/subscriptions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })

export const deleteSubscription = (id: string): Promise<{ deleted: boolean }> =>
  fetchJson(`${BASE}/subscriptions/${id}`, { method: 'DELETE' })

export const patchSubscription = (id: string, enabled: boolean): Promise<{ enabled: boolean }> =>
  fetchJson(`${BASE}/subscriptions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  })

export const runSubscription = (id: string): Promise<{ status: string; error?: string }> =>
  fetchJson(`${BASE}/subscriptions/${id}/run`, { method: 'POST' })

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
  fetchJson(`${BASE}/history/qlog?n=${n}`)

export const deleteQlog = (indices: number[]): Promise<{ deleted: number }> =>
  fetchJson(`${BASE}/history/qlog/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ indices }),
  })

export const clearQlog = (): Promise<{ cleared: boolean }> =>
  fetchJson(`${BASE}/history/qlog/clear`, { method: 'POST' })

export const qlogExportUrl = `${BASE}/history/qlog/export`

// ── Favorites ───────────────────────────────────────────────────────

export interface Favorite {
  id: string
  name: string
  sql: string
  question: string
  ds_type: string
  params: string[]
  created_at: string
}

export const fetchFavorites = (): Promise<{ favorites: Favorite[] }> =>
  fetchJson(`${BASE}/favorites`)

export const saveFavorite = (
  name: string,
  sql: string,
  question = '',
  ds_type = '',
): Promise<{ favorite: Favorite }> =>
  fetchJson(`${BASE}/favorites`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, sql, question, ds_type }),
  })

export const renameFavorite = (id: string, name: string): Promise<{ renamed: boolean }> =>
  fetchJson(`${BASE}/favorites/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })

export const deleteFavorite = (id: string): Promise<{ deleted: boolean }> =>
  fetchJson(`${BASE}/favorites/${id}`, { method: 'DELETE' })

export const sendFeedback = (
  sessionId: string,
  question: string,
  sql: string,
  positive: boolean,
): Promise<{ ok: boolean; positive: boolean }> =>
  fetchJson(`${BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, question, sql, positive }),
  })

export const fetchSavedSessions = (): Promise<{ sessions: SavedSession[] }> =>
  fetchJson(`${BASE}/history/sessions`)

export const resumeSaved = (
  sid: string,
  savedId: string,
): Promise<{ title: string; chat: { role: string; content: string }[] }> =>
  fetchJson(`${BASE}/session/${sid}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ saved_id: savedId }),
  })
