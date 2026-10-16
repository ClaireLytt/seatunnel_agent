import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { chatStream, resetSession, stopChat, type ChatEvent, type SessionMeta } from '@/api'
import { ResultBlock, type ResultData } from '@/ResultBlock'

type Item =
  | { kind: 'user'; text: string }
  | { kind: 'text'; text: string }
  | ({ kind: 'result' } & ResultData)
  | { kind: 'final'; text: string; stopped?: boolean }
  | { kind: 'error'; text: string }

export function ChatPanel({
  session,
  onSessionReset,
}: {
  session: SessionMeta
  onSessionReset: (s: SessionMeta) => void
}) {
  const { t } = useTranslation()
  const [items, setItems] = useState<Item[]>([])
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight)
  }, [items])

  const send = async () => {
    const q = input.trim()
    if (!q || running) return
    setInput('')
    setRunning(true)
    setItems((xs) => [...xs, { kind: 'user', text: q }])
    try {
      await chatStream(session.session_id, q, (e: ChatEvent) => {
        if (e.type === 'text') setItems((xs) => [...xs, { kind: 'text', text: e.text }])
        else if (e.type === 'delta')
          setItems((xs) => {
            const last = xs[xs.length - 1]
            if (last && last.kind === 'text')
              return [...xs.slice(0, -1), { kind: 'text', text: last.text + e.text }]
            return [...xs, { kind: 'text', text: e.text }]
          })
        else if (e.type === 'result')
          setItems((xs) => [
            ...xs,
            {
              kind: 'result',
              sql: e.sql,
              columns: e.columns,
              rows: e.rows,
              row_count: e.row_count,
            },
          ])
        else if (e.type === 'final')
          setItems((xs) => [...xs, { kind: 'final', text: e.text, stopped: e.stopped }])
        else if (e.type === 'error') setItems((xs) => [...xs, { kind: 'error', text: e.message }])
      })
    } catch (e) {
      setItems((xs) => [...xs, { kind: 'error', text: e instanceof Error ? e.message : String(e) }])
    } finally {
      setRunning(false)
    }
  }

  const newChat = async () => {
    const meta = await resetSession(session.session_id)
    onSessionReset(meta)
    setItems([])
  }

  return (
    <Card className="st-chat flex h-[78vh] flex-col">
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto pr-1">
        {items.map((it, i) =>
          it.kind === 'result' ? (
            <ResultBlock key={i} data={it} />
          ) : (
            <div
              key={i}
              className={
                it.kind === 'user'
                  ? 'st-msg-user ml-auto max-w-[80%] rounded border border-ink bg-ink px-3 py-2 text-sm text-paper'
                  : it.kind === 'error'
                    ? 'max-w-[90%] rounded border border-accent px-3 py-2 font-mono text-sm text-accent'
                    : 'st-msg-bot max-w-[90%] rounded border border-line bg-paper px-3 py-2 text-sm text-fg'
              }
            >
              {it.text}
              {it.kind === 'final' && it.stopped ? ' ⏹' : ''}
            </div>
          ),
        )}
      </div>
      <div className="mt-3 flex gap-2">
        <input
          className="flex-1 rounded border border-line bg-card px-3 py-2 text-sm text-fg outline-none focus:border-ink"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder={t('askPh')}
        />
        {running ? (
          <button
            onClick={() => stopChat(session.session_id)}
            className="rounded border-[1.5px] border-accent px-4 py-2 font-mono text-sm text-accent"
          >
            {t('stop')}
          </button>
        ) : (
          <button
            onClick={send}
            className="rounded border-[1.5px] border-ink bg-ink px-5 py-2 font-mono text-sm text-paper transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
          >
            {t('send')}
          </button>
        )}
        <button
          onClick={newChat}
          disabled={running}
          className="rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm text-ink disabled:opacity-50"
        >
          {t('newChat')}
        </button>
      </div>
    </Card>
  )
}
