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

// ── Report persistence (ticket 07) ──

export interface ReportSaveResult {
  ok: boolean
  filename?: string
  error?: string
}

export async function saveReport(params: {
  session_id: string
  table_a: string
  table_b: string
  lang: string
}): Promise<ReportSaveResult> {
  return json(
    await fetch(`${BASE}/reports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    }),
    'save report',
  )
}

export async function listReports(): Promise<string[]> {
  const data = await json<{ files: string[] }>(await fetch(`${BASE}/reports`), 'reports')
  return data.files
}

export async function loadReport(name: string, sessionId: string, lang: string): Promise<string> {
  const data = await json<{ html: string }>(
    await fetch(
      `${BASE}/reports/${encodeURIComponent(name)}?session_id=${encodeURIComponent(sessionId)}&lang=${lang}`,
    ),
    'load report',
  )
  return data.html
}

export async function diffReports(oldName: string, newName: string, lang: string): Promise<string> {
  const data = await json<{ html: string }>(
    await fetch(`${BASE}/reports/diff`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old: oldName, new: newName, lang }),
    }),
    'diff reports',
  )
  return data.html
}

// GET endpoints used as plain links (downloads / standalone view in new tab)
export const exportUrl = (fmt: 'csv' | 'xlsx', sessionId: string, lang: string) =>
  `${BASE}/export/${fmt}?session_id=${encodeURIComponent(sessionId)}&lang=${lang}`

export const standaloneReportUrl = (sessionId: string, lang: string) =>
  `${BASE}/report/standalone?session_id=${encodeURIComponent(sessionId)}&lang=${lang}`

export async function deletePreset(name: string): Promise<void> {
  await json(
    await fetch(`${BASE}/presets/${encodeURIComponent(name)}`, { method: 'DELETE' }),
    'delete preset',
  )
}
