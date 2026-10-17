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
  fetch(`${BASE}/templates`).then(j)

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
  fetch(`${BASE}/metrics`).then(j)

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
  fetch(`${BASE}/boards`).then(j)

export const createBoard = (name: string): Promise<{ board: Board }> =>
  fetch(`${BASE}/boards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  }).then(j)

export const deleteBoard = (id: string): Promise<{ deleted: boolean }> =>
  fetch(`${BASE}/boards/${id}`, { method: 'DELETE' }).then(j)

export const pinToBoard = (
  boardId: string,
  title: string,
  sql: string,
  ds_type = '',
): Promise<{ item: BoardItem }> =>
  fetch(`${BASE}/boards/${boardId}/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, sql, ds_type }),
  }).then(j)

export const renderBoard = (
  boardId: string,
  sessionId: string,
): Promise<{ results: { id: string; title: string; sql: string; columns?: string[]; rows?: unknown[][]; row_count?: number; error?: string }[] }> =>
  fetch(`${BASE}/boards/${boardId}/render?session_id=${sessionId}`).then(j)

// ── Subscriptions ───────────────────────────────────────────────────

export interface Subscription {
  id: string
  name: string
  cron: string
  source_type: string
  metric: string
  favorite_id: string
  webhook_url: string
  enabled: boolean
  last_run_at: string
  last_status: string
  last_error: string
}

export const fetchSubscriptions = (): Promise<{ subscriptions: Subscription[] }> =>
  fetch(`${BASE}/subscriptions`).then(j)

export const createSubscription = (
  data: { name: string; cron: string; source_type: string; metric?: string; favorite_id?: string; ds_type?: string; connection?: string; database?: string; webhook_url?: string; lang?: string },
): Promise<{ subscription: Subscription }> =>
  fetch(`${BASE}/subscriptions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(j)

export const deleteSubscription = (id: string): Promise<{ deleted: boolean }> =>
  fetch(`${BASE}/subscriptions/${id}`, { method: 'DELETE' }).then(j)

export const patchSubscription = (id: string, enabled: boolean): Promise<{ enabled: boolean }> =>
  fetch(`${BASE}/subscriptions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  }).then(j)

export const runSubscription = (id: string): Promise<{ status: string }> =>
  fetch(`${BASE}/subscriptions/${id}/run`, { method: 'POST' }).then(j)

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
  fetch(`${BASE}/favorites`).then(j)

export const saveFavorite = (
  name: string,
  sql: string,
  question = '',
  ds_type = '',
): Promise<{ favorite: Favorite }> =>
  fetch(`${BASE}/favorites`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, sql, question, ds_type }),
  }).then(j)

export const renameFavorite = (id: string, name: string): Promise<{ renamed: boolean }> =>
  fetch(`${BASE}/favorites/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  }).then(j)

export const deleteFavorite = (id: string): Promise<{ deleted: boolean }> =>
  fetch(`${BASE}/favorites/${id}`, { method: 'DELETE' }).then(j)

export const sendFeedback = (
  sessionId: string,
  question: string,
  sql: string,
  positive: boolean,
): Promise<{ ok: boolean; positive: boolean }> =>
  fetch(`${BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, question, sql, positive }),
  }).then(j)

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
