import { postSSE } from '@shared/sse'

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

// ── Global comparison options (frontend state; rides on action calls) ──
// Field names match the backend CompareRequest model (api.py).

export interface CompareOptions {
  where: string
  threshold: string
  key_columns: string
  column_mapping: string
  strategy: string
  stratified_col: string
  masking: boolean
}

export const OPTIONS_DEFAULTS: CompareOptions = {
  where: '',
  threshold: '',
  key_columns: '',
  column_mapping: '',
  strategy: 'TOP N',
  stratified_col: '',
  masking: true,
}

// ── Feature accordions (ticket 06) ──
// Field names match the backend FeatureRequest model (features.py).

export type FeatureAction =
  | 'incremental'
  | 'quality'
  | 'skew'
  | 'checksum'
  | 'chunked'
  | 'partition'
  | 'custom-agg'
  | 'sql'

export interface FeatureFields {
  watermark_col?: string
  watermark_val?: string
  quality_rules?: string
  skew_columns?: string
  checksum_columns?: string
  partition_col?: string
  expressions?: string
  sql_a?: string
  sql_b?: string
}

export async function featureAction(
  action: FeatureAction,
  params: {
    session_id: string
    table_a: string
    table_b: string
    lang: string
  } & CompareOptions &
    FeatureFields,
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

// ── Compound actions with progress (ticket 04) ──

export interface ProgressEvent {
  event: 'progress'
  value: number
  desc: string
}

export interface DoneEvent {
  event: 'done'
  html: string
}

export type CompoundEvent = ProgressEvent | DoneEvent

export type StreamAction = 'all' | 'batch-count' | 'batch-full'

export interface CompoundParams extends CompareOptions {
  session_id: string
  table_a: string
  table_b: string
  lang: string
}

// POST + SSE: progress frames feed onProgress, resolves with the final html.
export async function compareStream(
  action: StreamAction,
  params: CompoundParams,
  onProgress: (value: number, desc: string) => void,
): Promise<string> {
  let html = ''
  await postSSE<CompoundEvent>(`${BASE}/compare/${action}`, params, (e) => {
    if (e.event === 'progress') onProgress(e.value, e.desc)
    else if (e.event === 'done') html = e.html
  })
  return html
}

export async function compareProfile(params: CompoundParams): Promise<string> {
  const data = await json<{ html: string }>(
    await fetch(`${BASE}/compare/profile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    }),
    'profile',
  )
  return data.html
}
