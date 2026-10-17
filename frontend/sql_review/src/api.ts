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
  line_links?: boolean
  source?: 'api' | 'ui'
}

export interface FixRequest {
  sql: string
  dialect: string
  mode: 'static' | 'agent'
  report?: string
  rules?: Record<string, unknown>
  lang: 'zh' | 'en'
}

export interface FixResponse {
  fixed_sql: string
  report: string
  dialect: string
  elapsed_ms: number
}

export interface ReviewResponse {
  report: string
  findings: Record<string, unknown>[]
  stats: Record<string, number>
  dialect: string
  elapsed_ms: number
  warnings: string[]
}

export interface TopCategory {
  category: string
  label: string
  count: number
}

export interface StatsSummary {
  reviews: number
  findings: number
  severities: Record<string, number>
  top_categories: TopCategory[]
}

export interface DailyStat {
  day: string
  critical: number
  risk: number
  suggestion: number
}

export interface StatsResponse {
  summary: StatsSummary
  daily: DailyStat[]
}

// Dialect aliases accepted in ?dialect= deep links (mirrors linter._DIALECT_ALIASES)
export const DIALECT_ALIASES: Record<string, Dialect> = {
  odps: 'maxcompute',
  sparksql: 'spark',
  flinksql: 'flink',
  hivesql: 'hive',
  postgres: 'postgresql',
  pg: 'postgresql',
  mssql: 'sqlserver',
  tsql: 'sqlserver',
  ck: 'clickhouse',
}

const BASE = '/api/sql_review'

// carries the HTTP status so callers can branch on it instead of matching
// the detail wording
export class ApiError extends Error {
  status: number
  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
  }
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: `HTTP ${r.status}` }))
    throw new ApiError(
      r.status,
      typeof data.detail === 'string' ? data.detail : `HTTP ${r.status}`,
    )
  }
  return r.json()
}

export const review = (req: ReviewRequest) => post<ReviewResponse>('/review', req)
export const fix = (req: FixRequest) => post<FixResponse>('/fix', req)

export async function fetchStats(): Promise<StatsResponse> {
  const r = await fetch(`${BASE}/stats`)
  if (!r.ok) throw new Error(`stats: HTTP ${r.status}`)
  return r.json()
}
