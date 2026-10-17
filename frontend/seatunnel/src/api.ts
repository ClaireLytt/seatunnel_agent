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

export async function fetchMeta(): Promise<Meta> {
  const resp = await fetch('/api/seatunnel/meta')
  if (!resp.ok) throw new Error(`meta: HTTP ${resp.status}`)
  return resp.json()
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

export async function stopChat(conversationId: string, lang?: string): Promise<void> {
  const resp = await fetch('/api/seatunnel/chat/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, lang: lang ?? 'en' }),
  })
  if (!resp.ok) throw new Error(`stop: HTTP ${resp.status}`)
}
