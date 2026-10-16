import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { filterTables, reloadSchema, type SessionMeta } from '@/api'

/** Sidebar table whitelist: search, checkboxes, select/clear-all, confirm.
 *  The full table list comes from the connect/reload session meta and is
 *  the widening source after a narrow. */
export function SchemaPanel({
  session,
  fullTables,
  onSession,
  onFullTables,
}: {
  session: SessionMeta
  fullTables: string[]
  onSession: (s: SessionMeta) => void
  onFullTables: (t: string[]) => void
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [checked, setChecked] = useState<Set<string>>(new Set(session.tables))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => setChecked(new Set(session.tables)), [session])

  const visible = fullTables.filter((n) => n.toLowerCase().includes(search.toLowerCase()))

  const apply = async () => {
    setBusy(true)
    setErr('')
    try {
      onSession(await filterTables(session.session_id, [...checked]))
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const reload = async () => {
    setBusy(true)
    setErr('')
    try {
      const meta = await reloadSchema(session.session_id)
      onSession(meta)
      onFullTables(meta.tables)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="st-schema-panel space-y-2">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setOpen((o) => !o)}
          className="font-mono text-[12px] uppercase tracking-[0.18em] text-ink-soft"
        >
          {open ? '▾' : '▸'} {t('tableFilter')} ({session.table_count}/{fullTables.length})
        </button>
        <button
          onClick={reload}
          disabled={busy}
          title={t('reloadSchema')}
          className="rounded border border-line px-2 font-mono text-[12px] text-muted disabled:opacity-40"
        >
          ⟳
        </button>
      </div>
      {open && (
        <div className="space-y-2">
          <input
            className="w-full rounded border border-line bg-card px-2 py-1 font-mono text-[12px] text-fg outline-none focus:border-ink"
            placeholder={t('searchTables')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="max-h-44 space-y-1 overflow-y-auto font-mono text-[12px]">
            {visible.map((n) => (
              <label key={n} className="flex items-center gap-2 text-fg">
                <input
                  type="checkbox"
                  checked={checked.has(n)}
                  onChange={(e) =>
                    setChecked((c) => {
                      const next = new Set(c)
                      if (e.target.checked) next.add(n)
                      else next.delete(n)
                      return next
                    })
                  }
                  className="accent-[var(--ink)]"
                />
                {n}
              </label>
            ))}
          </div>
          <div className="flex items-center gap-2 font-mono text-[12px]">
            <button
              onClick={() => setChecked(new Set(fullTables))}
              className="rounded border border-line px-2 text-muted"
            >
              {t('selectAll')}
            </button>
            <button
              onClick={() => setChecked(new Set())}
              className="rounded border border-line px-2 text-muted"
            >
              {t('clearAll')}
            </button>
            <button
              onClick={apply}
              disabled={busy || checked.size === 0}
              className="st-filter-apply ml-auto rounded border-[1.5px] border-ink bg-ink px-3 py-0.5 text-paper disabled:opacity-40"
            >
              {t('applyFilter')}
            </button>
          </div>
          {err && <div className="font-mono text-[12px] text-accent">{err}</div>}
        </div>
      )}
    </Card>
  )
}
