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
