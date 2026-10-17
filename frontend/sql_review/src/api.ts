// Thin client for the SQL Review REST API (agents/data/sql_review/api.py).

export const DIALECTS = [
  'hive',
  'spark',
  'flink',
  'maxcompute',
  'mysql',
  'postgresql',
  'sqlserver',
  'clickhouse',
  'doris',
  'sqlite',
] as const

export type Dialect = (typeof DIALECTS)[number]

// Mirrors prompts.DIALECT_NAMES (display labels, language-neutral).
export const DIALECT_NAMES: Record<Dialect, string> = {
  hive: 'Hive SQL',
  spark: 'Spark SQL',
  flink: 'Flink SQL',
  maxcompute: 'MaxCompute SQL',
  mysql: 'MySQL',
  postgresql: 'PostgreSQL',
  sqlserver: 'SQL Server (T-SQL)',
  clickhouse: 'ClickHouse SQL',
  doris: 'Apache Doris SQL',
  sqlite: 'SQLite',
}

export interface ReviewRequest {
  sql: string
  dialect: string
  mode: 'static' | 'agent'
  schema_ddl?: string
  rules?: Record<string, unknown>
  lang: 'zh' | 'en'
}

export interface ReviewResponse {
  report: string
  findings: Record<string, unknown>[]
  stats: Record<string, number>
  dialect: string
  elapsed_ms: number
  warnings: string[]
}

const BASE = '/api/sql_review'

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
    throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${r.status}`)
  }
  return r.json()
}

export const review = (req: ReviewRequest) => post<ReviewResponse>('/review', req)
