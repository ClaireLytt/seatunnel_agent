import { postSSE } from '@shared/sse'

export interface StepEvent {
  type: 'step'
  tool: string
  elapsed_ms: number
  error: boolean
}

export interface DoneEvent {
  type: 'done'
  success: boolean
  reply: string
  steps: { tool: string; elapsed_ms: number; error: boolean }[]
  diff: string
  workdir: string
  final_test_output: string
  truncated: boolean
  elapsed_ms: number
}

export type RunEvent = StepEvent | DoneEvent | { type: 'error'; message: string }

const BASE = '/api/codefix'

export async function runFix(
  body: {
    path: string
    tests: string
    instruction: string
    max_steps: number
    lang: string
  },
  onEvent: (e: RunEvent) => void,
): Promise<void> {
  await postSSE<RunEvent>(`${BASE}/run`, body, onEvent)
}
