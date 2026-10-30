import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { chatStream, demoStream, stopChat, uploadFile, type ChatEvent } from '@/api'

// Chat round-trip: message in, SSE event stream out, Stop interrupts.
// Delta/flush semantics mirror the legacy ui.py format_events_as_chat:
// deltas accumulate into a trailing streaming bubble; a `text` event
// replaces the buffer, any other event flushes it as its own message.
// The ▌ cursor is a render-time suffix on the live streaming bubble only
// (the legacy formatter baked it into flushed history — a rendering bug,
// fixed both here and in rendering.py's format_events_as_chat).

// Flush the trailing streaming bubble into a permanent message.
// `replaced` drops it instead (a `text` event carries the full reply).
function flushStream(xs: Item[], replaced = false): Item[] {
  const last = xs[xs.length - 1]
  if (!last || last.kind !== 'stream') return xs
  const head = xs.slice(0, -1)
  return replaced ? head : [...head, { kind: 'event', text: last.text }]
}

type Item =
  | { kind: 'user'; text: string }
  | { kind: 'stream'; text: string }
  | { kind: 'event'; text: string }
  | { kind: 'error'; text: string }

export function Chat({
  emptyHint,
  mode = 'nl',
  configPath = '',
  templatePrompt = '',
  onConfigPath,
  initialConversationId = null,
  initialMessages = [],
  onTurnEnd,
}: {
  emptyHint: string
  mode?: string
  configPath?: string
  templatePrompt?: string
  onConfigPath?: (path: string) => void
  // session restore: remount (via key) with the loaded session's id + messages
  initialConversationId?: string | null
  initialMessages?: { role: string; content: string }[]
  onTurnEnd?: (conversationId: string | null) => void
}) {
  const { t, i18n } = useTranslation()
  const [items, setItems] = useState<Item[]>(() =>
    initialMessages.map((m) =>
      m.role === 'user'
        ? { kind: 'user' as const, text: m.content }
        : { kind: 'event' as const, text: m.content },
    ),
  )
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const convRef = useRef<string | null>(initialConversationId)
  const scrollRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // template selection fills the input (legacy template_dd.change behaviour)
  useEffect(() => {
    setInput(templatePrompt)
  }, [templatePrompt])

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
      setItems((xs) => [...flushStream(xs, e.kind === 'text'), { kind: 'event', text: e.markdown }])
    } else if (e.type === 'final') {
      setItems((xs) => {
        const head = flushStream(xs)
        const tail: Item[] = []
        if (e.error) tail.push({ kind: 'error', text: t('errorLabel', { msg: e.error }) })
        if (e.elapsed !== undefined)
          tail.push({ kind: 'event', text: t('completedIn', { s: e.elapsed.toFixed(1) }) })
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
      onTurnEnd?.(convRef.current)
    }
  }

  const stop = () => {
    if (convRef.current) void stopChat(convRef.current, i18n.language)
  }

  const runDemo = async () => {
    if (running) return
    const msg = input.trim() || t('demoDefaultMsg')
    setInput('')
    setRunning(true)
    setItems((xs) => [...xs, { kind: 'user', text: msg }])
    try {
      await demoStream({ config_path: configPath, lang: i18n.language }, onEvent)
    } catch (e) {
      setItems((xs) => [...xs, { kind: 'error', text: e instanceof Error ? e.message : String(e) }])
    } finally {
      setRunning(false)
    }
  }

  const onUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      const path = await uploadFile(file)
      onConfigPath?.(path)
    } catch (err) {
      setItems((xs) => [
        ...xs,
        { kind: 'error', text: err instanceof Error ? err.message : String(err) },
      ])
    }
  }

  return (
    <>
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto pr-1">
        {items.length === 0 && (
          // legacy ui.py _build_placeholder: logo, title, three hint cards
          // (click fills the input — ui.py hint-card delegation JS), docs link
          <div className="st-empty-state flex h-full flex-col items-center justify-center gap-4">
            <div className="st-empty-logo flex h-12 w-12 items-center justify-center rounded border-[1.5px] border-ink font-mono text-lg font-bold text-ink">
              ST
            </div>
            <div className="st-empty-title font-mono text-sm text-muted">{emptyHint}</div>
            <div className="st-empty-hints flex flex-wrap justify-center gap-2">
              {(['placeholderHint1', 'placeholderHint2', 'placeholderHint3'] as const).map((k) => (
                <button
                  key={k}
                  onClick={() => setInput(t(k))}
                  className="st-hint-card rounded border border-line bg-card px-3 py-2 font-mono text-xs text-fg transition hover:border-ink"
                >
                  {t(k)}
                </button>
              ))}
            </div>
            <a
              href="https://github.com/ClaireLytt/seatunnel_agent#readme"
              target="_blank"
              rel="noreferrer"
              className="st-docs-link font-mono text-xs text-muted underline hover:text-ink"
            >
              {t('docsLink')}
            </a>
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
          ref={fileRef}
          type="file"
          accept=".conf,.hocon,.config,.json"
          className="hidden"
          onChange={onUpload}
          aria-label={t('upload')}
        />
        <button
          onClick={() => fileRef.current?.click()}
          aria-label={t('upload')}
          title={t('upload')}
          className="st-btn-upload rounded border-[1.5px] border-line px-4 py-2 font-mono text-sm text-ink transition hover:border-ink"
        >
          +
        </button>
        <input
          className="flex-1 rounded border border-line bg-card px-3 py-2 font-mono text-sm text-fg outline-none focus:border-ink"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder={t('inputPlaceholder')}
          aria-label={t('inputPlaceholder')}
        />
        <button
          onClick={runDemo}
          disabled={running}
          className="st-btn-demo rounded border-[1.5px] border-line px-4 py-2 font-mono text-sm text-ink transition enabled:hover:border-ink disabled:opacity-50"
        >
          {t('demo')}
        </button>
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
