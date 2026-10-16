const BASE = '/api/text2sql'

// Mirrors executor.DS_TYPES; sqlite needs only a file path.
export const DS_TYPES = [
  'hive',
  'mysql',
  'sqlserver',
  'sparksql',
  'clickhouse',
  'doris',
  'postgresql',
  'sqlite',
  'flinksql',
] as const
export type DsType = (typeof DS_TYPES)[number]

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
