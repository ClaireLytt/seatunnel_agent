import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { chatStream, stopChat, type ChatEvent } from '@/api'

// Chat round-trip: message in, SSE event stream out, Stop interrupts.
// Delta/flush semantics mirror the legacy ui.py _format_events_as_chat:
// deltas accumulate into a trailing streaming bubble (▌ cursor); a `text`
// event replaces the buffer, any other event flushes it as its own message.

type Item =
  | { kind: 'user'; text: string }
  | { kind: 'stream'; text: string }
  | { kind: 'event'; text: string }
  | { kind: 'error'; text: string }

export function Chat({
  emptyHint,
  mode = 'nl',
  configPath = '',
}: {
  emptyHint: string
  mode?: string
  configPath?: string
}) {
  const { t, i18n } = useTranslation()
  const [items, setItems] = useState<Item[]>([])
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const convRef = useRef<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight)
  }, [items])

  const onEvent = (e: ChatEvent) => {
    if (e.type === 'conversation') {
      convRef.current = e.id
    } else if (e.type === 'delta') {
      setItems((xs) => {
        const last = xs[xs.length - 1]
        if (last && last.kind === 'stream')
          return [...xs.slice(0, -1), { kind: 'stream', text: last.text + e.text }]
        return [...xs, { kind: 'stream', text: e.text }]
      })
    } else if (e.type === 'event') {
      setItems((xs) => {
        const last = xs[xs.length - 1]
        const head =
          last && last.kind === 'stream'
            ? e.kind === 'text'
              ? xs.slice(0, -1) // text replaces the streamed buffer
              : [...xs.slice(0, -1), { kind: 'event' as const, text: last.text + ' ▌' }]
            : xs
        return [...head, { kind: 'event', text: e.markdown }]
      })
    } else if (e.type === 'final') {
      setItems((xs) => {
        const last = xs[xs.length - 1]
        const head =
          last && last.kind === 'stream'
            ? [...xs.slice(0, -1), { kind: 'event' as const, text: last.text + ' ▌' }]
            : xs
        const tail: Item[] = []
        if (e.error) tail.push({ kind: 'error', text: `⚠️ **Error**: ${e.error}` })
        if (e.elapsed !== undefined)
          tail.push({ kind: 'event', text: `⏱️ Completed in ${e.elapsed.toFixed(1)}s` })
        return [...head, ...tail]
      })
    }
  }

  const send = async () => {
    const msg = input.trim()
    if (!msg || running) return
    setInput('')
    setRunning(true)
    setItems((xs) => [...xs, { kind: 'user', text: msg }])
    try {
      await chatStream(
        {
          message: msg,
          conversation_id: convRef.current,
          mode,
          config_path: configPath,
          lang: i18n.language,
        },
        onEvent,
      )
    } catch (e) {
      setItems((xs) => [...xs, { kind: 'error', text: e instanceof Error ? e.message : String(e) }])
    } finally {
      setRunning(false)
    }
  }

  const stop = () => {
    if (convRef.current) void stopChat(convRef.current, i18n.language)
  }

  return (
    <>
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto pr-1">
        {items.length === 0 && (
          <div className="flex h-full items-center justify-center font-mono text-sm text-muted">
            {emptyHint}
          </div>
        )}
        {items.map((it, i) => (
          <div
            key={i}
            className={
              it.kind === 'user'
                ? 'st-msg-user ml-auto max-w-[80%] whitespace-pre-wrap rounded border border-ink bg-ink px-3 py-2 text-sm text-paper'
                : it.kind === 'error'
                  ? 'max-w-[90%] whitespace-pre-wrap rounded border border-accent px-3 py-2 font-mono text-sm text-accent'
                  : 'st-msg-bot max-w-[90%] whitespace-pre-wrap rounded border border-line bg-paper px-3 py-2 text-sm text-fg'
            }
          >
            {it.kind === 'stream' ? it.text + ' ▌' : it.text}
          </div>
        ))}
      </div>
      <div className="mt-4 flex gap-2 border-t border-line pt-4">
        <input
          className="flex-1 rounded border border-line bg-card px-3 py-2 font-mono text-sm text-fg outline-none focus:border-ink"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder={t('inputPlaceholder')}
          aria-label={t('inputPlaceholder')}
        />
        {running ? (
          <button
            onClick={stop}
            aria-label={t('stop')}
            className="st-btn-stop rounded border-[1.5px] border-accent px-4 py-2 font-mono text-sm text-accent"
          >
            ■
          </button>
        ) : (
          <button
            onClick={send}
            aria-label={t('send')}
            className="st-btn-send rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm text-paper transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
          >
            ➤
          </button>
        )}
      </div>
    </>
  )
}
