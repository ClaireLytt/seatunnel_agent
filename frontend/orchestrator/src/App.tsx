import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import {
  chatStream,
  clearSession,
  fetchAgents,
  fetchSession,
  type AgentSpec,
  type ChatEvent,
} from '@/api'

type Item =
  | { kind: 'user'; text: string }
  | { kind: 'step'; tool: string; ms: number; output: string }
  | { kind: 'reply'; text: string; suggestedOnly: boolean; toolsUsed?: string[] }
  | { kind: 'error'; text: string }

const MAX_STEP_OUTPUT = 4000

export default function App() {
  const { t, i18n } = useTranslation()
  const [items, setItems] = useState<Item[]>([])
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const [agents, setAgents] = useState<AgentSpec[]>([])
  const sessionRef = useRef<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // restore the most recent persisted session (same as the Gradio page)
  useEffect(() => {
    fetchSession()
      .then(({ session, turns }) => {
        if (!turns.length) return
        sessionRef.current = session
        const restored: Item[] = []
        for (const turn of turns) {
          restored.push({ kind: 'user', text: turn.request })
          restored.push({
            kind: 'reply',
            text: turn.reply,
            suggestedOnly: false,
            toolsUsed: turn.steps.length ? turn.steps.map((s) => s.tool) : undefined,
          })
        }
        setItems(restored)
      })
      .catch((e) => console.error(e))
    fetchAgents(i18n.language)
      .then(({ agents }) => setAgents(agents))
      .catch((e) => console.error(e))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight)
  }, [items, running])

  // plain turns re-seed the stateless backend's context (steps are skipped)
  const plainTurns = (xs: Item[]) => {
    const turns: { role: string; content: string }[] = []
    for (const it of xs) {
      if (it.kind === 'user') turns.push({ role: 'user', content: it.text })
      else if (it.kind === 'reply') turns.push({ role: 'assistant', content: it.text })
    }
    return turns
  }

  const send = async () => {
    const q = input.trim()
    if (!q || running) return
    setInput('')
    setRunning(true)
    const history = plainTurns(items)
    setItems((xs) => [...xs, { kind: 'user', text: q }])
    try {
      await chatStream(
        { request: q, lang: i18n.language, session: sessionRef.current, history },
        (e: ChatEvent) => {
          if (e.type === 'step')
            setItems((xs) => [
              ...xs,
              { kind: 'step', tool: e.tool, ms: e.elapsed_ms, output: e.output },
            ])
          else if (e.type === 'done') {
            sessionRef.current = e.session
            setItems((xs) => [
              ...xs,
              { kind: 'reply', text: e.reply, suggestedOnly: e.suggested_only },
            ])
          } else if (e.type === 'error')
            setItems((xs) => [...xs, { kind: 'error', text: e.message }])
        },
      )
    } catch (e) {
      setItems((xs) => [...xs, { kind: 'error', text: e instanceof Error ? e.message : String(e) }])
    } finally {
      setRunning(false)
    }
  }

  const newSession = async () => {
    try {
      await clearSession()
    } catch (e) {
      console.error(e)
    }
    sessionRef.current = null
    setItems([])
  }

  return (
    <div className="mx-auto max-w-[1020px] px-4 py-10">
      <PageHeader badge="ai / orchestrator" maxW="max-w-[620px]" />

      <Card className="st-chat mt-8 flex h-[70vh] flex-col">
        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto pr-1">
          {items.length === 0 && (
            <div className="mx-auto mt-10 max-w-[560px] text-center text-muted">
              <p className="font-display text-lg font-bold text-ink">{t('chatPhTitle')}</p>
              <p className="mt-3 text-sm">{t('chatPh')}</p>
              <p className="mt-3 text-sm italic">{t('chatPhChain')}</p>
            </div>
          )}
          {items.map((it, i) =>
            it.kind === 'user' ? (
              <div
                key={i}
                className="st-msg-user ml-auto max-w-[80%] whitespace-pre-wrap rounded border border-ink bg-ink px-3 py-2 text-sm text-paper"
              >
                {it.text}
              </div>
            ) : it.kind === 'step' ? (
              <details
                key={i}
                className="st-step max-w-[90%] rounded border border-line bg-paper px-3 py-2 text-sm text-fg"
              >
                <summary className="cursor-pointer font-mono text-ink-soft">
                  🔧 {it.tool} · {it.ms} ms
                </summary>
                <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap font-mono text-xs">
                  {it.output.length > MAX_STEP_OUTPUT
                    ? it.output.slice(0, MAX_STEP_OUTPUT) + '\n…'
                    : it.output}
                </pre>
              </details>
            ) : it.kind === 'error' ? (
              <div
                key={i}
                className="max-w-[90%] rounded border border-accent px-3 py-2 font-mono text-sm text-accent"
              >
                {it.text}
              </div>
            ) : (
              <div
                key={i}
                className="st-msg-bot max-w-[90%] rounded border border-line bg-paper px-3 py-2 text-sm text-fg"
              >
                {it.suggestedOnly && (
                  <p className="mb-2 font-mono text-xs text-ink-soft">{t('noKey')}</p>
                )}
                <ReportView markdown={it.text} className="st-md space-y-2" />
                {it.toolsUsed && (
                  <p className="mt-2 font-mono text-xs text-ink-soft">
                    🔧 {it.toolsUsed.join(', ')}
                  </p>
                )}
              </div>
            ),
          )}
          {running && <div className="text-sm text-muted">{t('working')}</div>}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {(
            [
              ['exReview', 'exReviewText'],
              ['exChain', 'exChainText'],
              ['exPii', 'exPiiText'],
            ] as const
          ).map(([label, textKey]) => (
            <button
              key={label}
              onClick={() => setInput(t(textKey))}
              disabled={running}
              className="rounded border border-line px-3 py-1 font-mono text-xs text-ink-soft transition hover:border-ink hover:text-ink disabled:opacity-50"
            >
              {t(label)}
            </button>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <textarea
            rows={3}
            className="flex-1 resize-none rounded border border-line bg-card px-3 py-2 text-sm text-fg outline-none focus:border-ink"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            placeholder={t('inputPh')}
          />
          <div className="flex flex-col gap-2">
            <button
              onClick={send}
              disabled={running}
              className="rounded border-[1.5px] border-ink bg-ink px-5 py-2 font-mono text-sm text-paper transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {t('send')}
            </button>
            <button
              onClick={newSession}
              disabled={running}
              className="rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm text-ink disabled:opacity-50"
            >
              {t('newSession')}
            </button>
          </div>
        </div>
      </Card>

      <details className="mt-6 rounded border border-line bg-card px-4 py-3">
        <summary className="cursor-pointer font-mono text-sm text-ink">{t('agentsAcc')}</summary>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line font-mono text-xs uppercase tracking-wide text-ink-soft">
                <th className="py-2 pr-4">{t('colAgent')}</th>
                <th className="py-2 pr-4">{t('colPage')}</th>
                <th className="py-2">{t('colDesc')}</th>
              </tr>
            </thead>
            <tbody>
              {[...agents]
                .sort((a, b) => a.name.localeCompare(b.name))
                .map((a) => (
                  <tr key={a.name} className="border-b border-line align-top last:border-b-0">
                    <td className="py-2 pr-4 font-mono text-xs text-ink">{a.name}</td>
                    <td className="py-2 pr-4 font-mono text-xs">
                      {a.page ? (
                        <a href={a.page} className="text-ink underline">
                          {a.page}
                        </a>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-2 text-fg">{a.description.slice(0, 110)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
