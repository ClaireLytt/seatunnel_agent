export interface Datasource {
  key: string
  label: string
  needs_host: boolean
  needs_auth: boolean
  default_port: number
  default_db: string
}

export interface Meta {
  datasources: Datasource[]
  sample_strategies: string[]
  schedule_intervals: string[]
}

export interface ConnectOk {
  ok: true
  status: string
  tables: string[]
  resolved: { host: string; port: number; database: string }
}

export interface ConnectErr {
  ok: false
  error: string
}

export type ConnectResult = ConnectOk | ConnectErr

export interface ConnectParams {
  session_id: string
  side: 'a' | 'b'
  ds_type: string
  host: string
  port: string
  db: string
  username: string
  password: string
  lang: string
}

const BASE = '/api/datacompare'

async function json<T>(r: Response, what: string): Promise<T> {
  if (!r.ok) throw new Error(`${what}: HTTP ${r.status}`)
  return r.json()
}

export async function fetchMeta(): Promise<Meta> {
  return json(await fetch(`${BASE}/meta`), 'meta')
}

export async function createSession(): Promise<string> {
  const data = await json<{ session_id: string }>(
    await fetch(`${BASE}/session`, { method: 'POST' }),
    'session',
  )
  return data.session_id
}

// Global comparison options. Defaults mirror the legacy page; the options
// block UI (ticket 05) plugs real values into the same object.
export interface CompareOptions {
  where: string
  threshold: string
  key_columns: string
  strategy: string
  column_mapping: string
  masking: boolean
  stratified_col: string
}

export const defaultCompareOptions: CompareOptions = {
  where: '',
  threshold: '',
  key_columns: '',
  strategy: 'TOP N',
  column_mapping: '',
  masking: true,
  stratified_col: '',
}

export type CoreAction = 'schema' | 'count' | 'sample' | 'aggregate'

export async function compareAction(
  action: CoreAction,
  params: {
    session_id: string
    table_a: string
    table_b: string
    lang: string
  } & CompareOptions,
): Promise<string> {
  const data = await json<{ html: string }>(
    await fetch(`${BASE}/compare/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    }),
    action,
  )
  return data.html
}

export async function connectSide(params: ConnectParams): Promise<ConnectResult> {
  return json(
    await fetch(`${BASE}/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    }),
    'connect',
  )
}
