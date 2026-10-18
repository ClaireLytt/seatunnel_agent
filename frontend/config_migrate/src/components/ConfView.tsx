import { type ReactNode, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

// Minimal in-house highlighter for the generated SeaTunnel HOCON config —
// no highlight-library precedent exists in frontend/ (checked sql_review /
// text2sql), so a ~40-line tokenizer beats adding a dependency. Tokens:
// comments, block names, keys, strings, numbers/booleans.
const TOKEN =
  /(#[^\n]*)|("(?:[^"\\]|\\.)*")|(\b(?:true|false)\b|-?\b\d+(?:\.\d+)?\b)|([\w.-]+)(?=\s*[={])/g

function highlightLine(line: string, key: number): ReactNode {
  const parts: ReactNode[] = []
  let last = 0
  let i = 0
  for (const m of line.matchAll(TOKEN)) {
    if (m.index! > last) parts.push(line.slice(last, m.index))
    const [, comment, str, num, name] = m
    const cls = comment
      ? 'italic text-muted'
      : str
        ? 'text-[var(--accent)]'
        : num
          ? 'text-[var(--ok)]'
          : name
            ? 'font-semibold text-ink'
            : ''
    parts.push(
      <span key={i++} className={cls}>
        {m[0]}
      </span>,
    )
    last = m.index! + m[0].length
  }
  if (last < line.length) parts.push(line.slice(last))
  return <div key={key}>{parts.length ? parts : ' '}</div>
}

export function ConfView({ conf }: { conf: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const lines = useMemo(() => conf.replace(/\n$/, '').split('\n'), [conf])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(conf)
    } catch {
      // clipboard API unavailable (http origin) — fall back silently
      const ta = document.createElement('textarea')
      ta.value = conf
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      ta.remove()
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
          {t('conf_label')}
        </span>
        <button
          onClick={copy}
          className="rounded border border-line px-3 py-1 font-mono text-xs text-ink transition hover:border-ink"
        >
          {copied ? `✓ ${t('copied')}` : t('copy')}
        </button>
      </div>
      <pre className="overflow-x-auto rounded border border-line bg-[var(--paper)] p-4 font-mono text-[13px] leading-relaxed">
        {lines.map((l, i) => highlightLine(l, i))}
      </pre>
    </div>
  )
}
