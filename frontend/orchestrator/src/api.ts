import { postSSE } from '@shared/sse'

export interface Step {
  tool: string
  elapsed_ms: number
  output: string
}

export type ChatEvent =
  | ({ type: 'step' } & Step)
  | {
      type: 'done'
      reply: string
      truncated: boolean
      suggested_only: boolean
      session: string | null
      elapsed_ms: number
    }
  | { type: 'error'; message: string }

export interface AgentSpec {
  name: string
  description: string
  page: string | null
  input_schema?: Record<string, unknown>
}

export interface SessionTurn {
  request: string
  reply: string
  steps: Step[]
}

const BASE = '/api/orchestrator'

export async function chatStream(
  body: {
    request: string
    lang: string
    session: string | null
    history: { role: string; content: string }[]
  },
  onEvent: (e: ChatEvent) => void,
): Promise<void> {
  await postSSE<ChatEvent>(`${BASE}/chat`, body, onEvent)
}

export async function fetchSession(): Promise<{ session: string | null; turns: SessionTurn[] }> {
  const r = await fetch(`${BASE}/session`)
  if (!r.ok) throw new Error(`session: HTTP ${r.status}`)
  return r.json()
}

export async function fetchAgents(lang: string): Promise<{ agents: AgentSpec[] }> {
  const r = await fetch(`${BASE}/agents?lang=${encodeURIComponent(lang)}`)
  if (!r.ok) throw new Error(`agents: HTTP ${r.status}`)
  return r.json()
}

export async function clearSession(): Promise<void> {
  const r = await fetch(`${BASE}/session/clear`, { method: 'POST' })
  if (!r.ok) throw new Error(`clear: HTTP ${r.status}`)
}
