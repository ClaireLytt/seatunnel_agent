import { fetchJson } from '@shared/api'

export interface Mode {
  key: string
  en: string
  zh: string
}

export interface TemplateMeta {
  name: string
  description: string
  category: string
  parameters: { name: string; default: string; description: string }[]
}

export interface Meta {
  modes: Mode[]
  templates: TemplateMeta[]
  config_placeholder: string
}

export type ConnectResult = { ok: true; model: string } | { ok: false; error: string }

export function connect(): Promise<ConnectResult> {
  return fetchJson('/api/seatunnel/connect', { method: 'POST' })
}

export function fetchMeta(): Promise<Meta> {
  return fetchJson('/api/seatunnel/meta')
}

// ── Sessions ─────────────────────────────────────────────────────────

export interface SessionSummary {
  id: string
  title: string
  updated_at: string
  msg_count: number
}

export interface SessionMessage {
  role: string
  content: string
}

export interface SessionDetail {
  id: string
  title: string
  messages: SessionMessage[]
}

export async function listSessions(): Promise<SessionSummary[]> {
  const data = await fetchJson<{ sessions: SessionSummary[] }>('/api/seatunnel/sessions')
  return data.sessions
}

export function loadSession(id: string): Promise<SessionDetail> {
  return fetchJson(`/api/seatunnel/sessions/${id}`)
}

export async function renameSession(id: string, title: string): Promise<void> {
  await fetchJson(`/api/seatunnel/sessions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

// Export downloads via a plain navigation (no fetch/stream logic needed).
export function exportSessionUrl(id: string): string {
  return `/api/seatunnel/sessions/${encodeURIComponent(id)}/export`
}

export async function deleteSession(id: string): Promise<void> {
  await fetchJson(`/api/seatunnel/sessions/${id}`, { method: 'DELETE' })
}

// ── Chat SSE ─────────────────────────────────────────────────────────

export type ChatEvent =
  | { type: 'conversation'; id: string }
  | { type: 'delta'; text: string }
  | { type: 'event'; kind: string; markdown: string }
  | { type: 'final'; elapsed?: number; error?: string; stopped?: boolean }

export interface ChatParams {
  message: string
  conversation_id?: string | null
  mode?: string
  config_path?: string
  lang?: string
}

export async function chatStream(
  params: ChatParams,
  onEvent: (e: ChatEvent) => void,
): Promise<void> {
  const { postSSE } = await import('@shared/sse')
  await postSSE<ChatEvent>('/api/seatunnel/chat', params, onEvent)
}

export async function demoStream(
  params: { config_path?: string; lang?: string },
  onEvent: (e: ChatEvent) => void,
): Promise<void> {
  const { postSSE } = await import('@shared/sse')
  await postSSE<ChatEvent>('/api/seatunnel/demo', params, onEvent)
}

export async function uploadFile(file: File): Promise<string> {
  const form = new FormData()
  form.append('file', file)
  const data = await fetchJson<{ path: string }>('/api/seatunnel/upload', {
    method: 'POST',
    body: form,
  })
  return data.path
}

export async function stopChat(conversationId: string, lang?: string): Promise<void> {
  await fetchJson('/api/seatunnel/chat/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, lang: lang ?? 'en' }),
  })
}
