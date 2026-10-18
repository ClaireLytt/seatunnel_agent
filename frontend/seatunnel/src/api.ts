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

export async function connect(): Promise<ConnectResult> {
  const resp = await fetch('/api/seatunnel/connect', { method: 'POST' })
  if (!resp.ok) throw new Error(`connect: HTTP ${resp.status}`)
  return resp.json()
}

export async function fetchMeta(): Promise<Meta> {
  const resp = await fetch('/api/seatunnel/meta')
  if (!resp.ok) throw new Error(`meta: HTTP ${resp.status}`)
  return resp.json()
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
  const resp = await fetch('/api/seatunnel/sessions')
  if (!resp.ok) throw new Error(`sessions: HTTP ${resp.status}`)
  return (await resp.json()).sessions
}

export async function loadSession(id: string): Promise<SessionDetail> {
  const resp = await fetch(`/api/seatunnel/sessions/${id}`)
  if (!resp.ok) throw new Error(`session: HTTP ${resp.status}`)
  return resp.json()
}

export async function renameSession(id: string, title: string): Promise<void> {
  const resp = await fetch(`/api/seatunnel/sessions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  if (!resp.ok) throw new Error(`rename: HTTP ${resp.status}`)
}

// Export downloads via a plain navigation (no fetch/stream logic needed).
export function exportSessionUrl(id: string): string {
  return `/api/seatunnel/sessions/${encodeURIComponent(id)}/export`
}

export async function deleteSession(id: string): Promise<void> {
  const resp = await fetch(`/api/seatunnel/sessions/${id}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`delete: HTTP ${resp.status}`)
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
  const resp = await fetch('/api/seatunnel/upload', { method: 'POST', body: form })
  if (!resp.ok) throw new Error(`upload: HTTP ${resp.status}`)
  const data = (await resp.json()) as { path: string }
  return data.path
}

export async function stopChat(conversationId: string, lang?: string): Promise<void> {
  const resp = await fetch('/api/seatunnel/chat/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, lang: lang ?? 'en' }),
  })
  if (!resp.ok) throw new Error(`stop: HTTP ${resp.status}`)
}
