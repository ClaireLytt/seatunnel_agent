import { fetchJson } from '@shared/api'
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

export function fetchSession(): Promise<{ session: string | null; turns: SessionTurn[] }> {
  return fetchJson(`${BASE}/session`)
}

export function fetchAgents(lang: string): Promise<{ agents: AgentSpec[] }> {
  return fetchJson(`${BASE}/agents?lang=${encodeURIComponent(lang)}`)
}

export async function clearSession(): Promise<void> {
  await fetchJson(`${BASE}/session/clear`, { method: 'POST' })
}
