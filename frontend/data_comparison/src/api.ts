import { fetchJson } from '@shared/api'
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

export async function fetchMeta(): Promise<Meta> {
  return fetchJson(`${BASE}/meta`)
}

export async function createSession(): Promise<string> {
  const data = await fetchJson<{ session_id: string }>(`${BASE}/session`, { method: 'POST' })
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
  const data = await fetchJson<{ html: string }>(`${BASE}/compare/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return data.html
}

export async function connectSide(params: ConnectParams): Promise<ConnectResult> {
  return fetchJson(`${BASE}/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
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
  'incremental' | 'quality' | 'skew' | 'checksum' | 'chunked' | 'partition' | 'custom-agg' | 'sql'

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
  const data = await fetchJson<{ html: string }>(`${BASE}/compare/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
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
  const data = await fetchJson<{ presets: PresetSummary[] }>(`${BASE}/presets`)
  return data.presets
}

export async function savePreset(p: PresetConnection & { name: string }): Promise<void> {
  await fetchJson(`${BASE}/presets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(p),
  })
}

export async function loadPreset(name: string): Promise<PresetConnection & { name: string }> {
  return fetchJson(`${BASE}/presets/${encodeURIComponent(name)}`)
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
  return fetchJson(`${BASE}/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
}

export async function listReports(): Promise<string[]> {
  const data = await fetchJson<{ files: string[] }>(`${BASE}/reports`)
  return data.files
}

export async function loadReport(name: string, sessionId: string, lang: string): Promise<string> {
  const data = await fetchJson<{ html: string }>(
    `${BASE}/reports/${encodeURIComponent(name)}?session_id=${encodeURIComponent(sessionId)}&lang=${lang}`,
  )
  return data.html
}

export async function diffReports(oldName: string, newName: string, lang: string): Promise<string> {
  const data = await fetchJson<{ html: string }>(`${BASE}/reports/diff`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ old: oldName, new: newName, lang }),
  })
  return data.html
}

// GET endpoints used as plain links (downloads / standalone view in new tab)
export const exportUrl = (fmt: 'csv' | 'xlsx', sessionId: string, lang: string) =>
  `${BASE}/export/${fmt}?session_id=${encodeURIComponent(sessionId)}&lang=${lang}`

export const standaloneReportUrl = (sessionId: string, lang: string) =>
  `${BASE}/report/standalone?session_id=${encodeURIComponent(sessionId)}&lang=${lang}`

export async function deletePreset(name: string): Promise<void> {
  await fetchJson(`${BASE}/presets/${encodeURIComponent(name)}`, { method: 'DELETE' })
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
  const data = await fetchJson<{ html: string }>(`${BASE}/compare/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return data.html
}

// ── Generation features (ticket 08) ──

export interface SyncConfigResult {
  html: string
  download_id: string | null
}

export async function generateSyncConfig(params: {
  session_id: string
  table_a: string
  table_b: string
  column_mapping: string
  lang: string
}): Promise<SyncConfigResult> {
  return fetchJson(`${BASE}/generate/sync-config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
}

// GET FileResponse carrying the real passwords — used as a plain link href.
export function syncConfigDownloadUrl(downloadId: string): string {
  return `${BASE}/generate/sync-config/download?id=${encodeURIComponent(downloadId)}`
}

export async function generateDiffSql(params: {
  session_id: string
  table_a: string
  table_b: string
  lang: string
}): Promise<string> {
  const data = await fetchJson<{ html: string }>(`${BASE}/generate/diff-sql`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return data.html
}

export async function traceLineage(params: {
  table: string
  sqls: string
  lang: string
}): Promise<string> {
  const data = await fetchJson<{ html: string }>(`${BASE}/lineage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return data.html
}

export async function compareEnvironments(params: {
  env_a: string
  env_b: string
  table: string
  where: string
  lang: string
}): Promise<string> {
  const data = await fetchJson<{ html: string }>(`${BASE}/compare/environments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return data.html
}

// ── Comparison templates (ticket 08) ──

export interface TemplateSummary {
  id: string
  name: string
  table_a: string
  table_b: string
  created_at: string
}

export interface ComparisonTemplate {
  name: string
  table_a: string
  table_b: string
  where_clause: string
  key_columns: string
  threshold: string
  column_mapping: string
  sample_strategy: string
  watermark_column: string
  quality_rules: string
  webhook_url: string
  notify_on_fail: boolean
  masking_enabled: boolean
}

export async function listTemplates(): Promise<TemplateSummary[]> {
  const data = await fetchJson<{ templates: TemplateSummary[] }>(`${BASE}/templates`)
  return data.templates
}

export async function saveTemplate(t: ComparisonTemplate): Promise<void> {
  await fetchJson(`${BASE}/templates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(t),
  })
}

export async function loadTemplate(name: string): Promise<ComparisonTemplate> {
  return fetchJson(`${BASE}/templates/${encodeURIComponent(name)}`)
}

export async function deleteTemplate(name: string): Promise<void> {
  await fetchJson(`${BASE}/templates/${encodeURIComponent(name)}`, { method: 'DELETE' })
}

// ── Schedule / webhook / trends (ticket 09) ──

export interface WebhookOptions {
  webhook_url: string
  notify_on_fail: boolean
}

export const WEBHOOK_DEFAULTS: WebhookOptions = {
  webhook_url: '',
  notify_on_fail: false,
}

export interface ScheduleResult {
  ok: boolean
  active: boolean
  message: string
}

export interface ScheduleStatus {
  active: boolean
  interval: number
  last_run: string | null
  last_error: string | null
}

export async function scheduleStart(
  params: CompoundParams & WebhookOptions & FeatureFields & { interval: string },
): Promise<ScheduleResult> {
  return fetchJson(`${BASE}/schedule/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
}

export async function scheduleStop(sessionId: string, lang: string): Promise<ScheduleResult> {
  return fetchJson(`${BASE}/schedule/stop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, lang }),
  })
}

export async function scheduleStatus(sessionId: string): Promise<ScheduleStatus> {
  return fetchJson(`${BASE}/schedule/status?session_id=${encodeURIComponent(sessionId)}`)
}

export interface TrendEntry {
  timestamp: string
  table_a: string
  table_b: string
  delta: number
  delta_pct: number
  mismatches: number
  schema_changes: number
  skew_top1: number | null
}

export interface TrendsResult {
  entries: TrendEntry[]
  alerts_html: string
}

export async function fetchTrends(lang: string, alertRules: string): Promise<TrendsResult> {
  const qs = new URLSearchParams({ lang, alert_rules: alertRules })
  return fetchJson(`${BASE}/trends?${qs}`)
}

export async function batchRunTemplates(params: {
  session_id: string
  names: string[]
  lang: string
}): Promise<string> {
  const data = await fetchJson<{ html: string }>(`${BASE}/templates/batch-run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return data.html
}
