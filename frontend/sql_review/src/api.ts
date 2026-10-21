// Thin client for the SQL Review REST API (agents/data/sql_review/api.py).

import { ApiError, fetchJson } from '@shared/api'

export { ApiError }

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

// non-2xx responses throw the shared ApiError{status, detail}, so callers
// can branch on the HTTP status instead of matching the detail wording
const post = <T,>(path: string, body: unknown): Promise<T> =>
  fetchJson<T>(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const review = (req: ReviewRequest) => post<ReviewResponse>('/review', req)
export const fix = (req: FixRequest) => post<FixResponse>('/fix', req)

export function fetchStats(): Promise<StatsResponse> {
  return fetchJson(`${BASE}/stats`)
}
