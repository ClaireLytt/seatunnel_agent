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

// ── Global comparison options (frontend state; rides on action calls) ──

export interface CompareOptions {
  where: string
  threshold: string
  key_columns: string
  column_mapping: string
  sample_strategy: string
  stratified_col: string
  masking: boolean
}

export const OPTIONS_DEFAULTS: CompareOptions = {
  where: '',
  threshold: '',
  key_columns: '',
  column_mapping: '',
  sample_strategy: 'TOP N',
  stratified_col: '',
  masking: true,
}

// ── Connection presets ──

export interface PresetSummary {
  id: string
  name: string
  environment: string
}

export interface PresetConnection {
  ds_type: string
  host: string
  port: number
  database: string
  username: string
  password: string
  environment: string
}

export async function listPresets(): Promise<PresetSummary[]> {
  const data = await json<{ presets: PresetSummary[] }>(
    await fetch(`${BASE}/presets`),
    'presets',
  )
  return data.presets
}

export async function savePreset(p: PresetConnection & { name: string }): Promise<void> {
  await json(
    await fetch(`${BASE}/presets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(p),
    }),
    'save preset',
  )
}

export async function loadPreset(name: string): Promise<PresetConnection & { name: string }> {
  return json(await fetch(`${BASE}/presets/${encodeURIComponent(name)}`), 'load preset')
}

export async function deletePreset(name: string): Promise<void> {
  await json(
    await fetch(`${BASE}/presets/${encodeURIComponent(name)}`, { method: 'DELETE' }),
    'delete preset',
  )
}
