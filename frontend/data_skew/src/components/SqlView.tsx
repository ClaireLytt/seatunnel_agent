import { useState } from 'react'
import { useTranslation } from 'react-i18next'

// Translated-SQL code block with a copy button (config_migrate ConfView
// precedent, minus the HOCON tokenizer — plain SQL text is fine here,
// matching the legacy gr.Code affordance).
export function SqlView({ sql }: { sql: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql)
    } catch {
      // clipboard API unavailable (http origin) — fall back silently
      const ta = document.createElement('textarea')
      ta.value = sql
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
          {t('optimized_sql')}
        </span>
        <button
          onClick={copy}
          className="rounded border border-line px-3 py-1 font-mono text-xs text-ink transition hover:border-ink"
        >
          {copied ? `✓ ${t('copied')}` : t('copy')}
        </button>
      </div>
      <pre className="overflow-x-auto rounded border border-line bg-[var(--paper)] p-4 font-mono text-[13px] leading-relaxed">
        {sql}
      </pre>
    </div>
  )
}
