import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { SessionSummary } from '@/api'

// Sidebar session list: new chat, load, inline rename, delete.
// Buttons/icons over explanatory text (project UI rules).

export function Sessions({
  sessions,
  activeId,
  onNew,
  onLoad,
  onRename,
  onDelete,
}: {
  sessions: SessionSummary[]
  activeId: string | null
  onNew: () => void
  onLoad: (id: string) => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
}) {
  const { t } = useTranslation()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  const confirmRename = () => {
    if (editingId && draft.trim()) onRename(editingId, draft.trim())
    setEditingId(null)
  }

  return (
    <div className="st-sessions">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
          {t('sessions')}
        </h2>
        <button
          onClick={onNew}
          aria-label={t('newChat')}
          title={t('newChat')}
          className="st-new-chat rounded border-[1.5px] border-ink bg-ink px-2 py-0.5 font-mono text-sm leading-none text-paper transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
        >
          +
        </button>
      </div>
      {sessions.length === 0 && (
        <p className="font-mono text-sm text-muted">{t('noSessions')}</p>
      )}
      <ul className="max-h-[320px] space-y-1 overflow-y-auto">
        {sessions.map((s) => (
          <li key={s.id} className="group">
            {editingId === s.id ? (
              <div className="flex items-center gap-1">
                <input
                  autoFocus
                  className="min-w-0 flex-1 rounded border border-ink bg-card px-2 py-1 font-mono text-xs text-fg outline-none"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') confirmRename()
                    if (e.key === 'Escape') setEditingId(null)
                  }}
                  aria-label={t('rename')}
                />
                <button
                  onClick={confirmRename}
                  aria-label={t('renameOk')}
                  className="rounded border border-ink px-1.5 py-0.5 font-mono text-xs text-ink hover:bg-ink hover:text-paper"
                >
                  ✓
                </button>
                <button
                  onClick={() => setEditingId(null)}
                  aria-label={t('renameCancel')}
                  className="rounded border border-line px-1.5 py-0.5 font-mono text-xs text-muted hover:border-ink hover:text-ink"
                >
                  ✕
                </button>
              </div>
            ) : (
              <div
                className={
                  'flex items-center gap-1 rounded border px-2 py-1 ' +
                  (s.id === activeId
                    ? 'border-ink bg-card'
                    : 'border-transparent hover:border-line hover:bg-card')
                }
              >
                <button
                  onClick={() => onLoad(s.id)}
                  className="st-session-item min-w-0 flex-1 text-left"
                  title={s.title}
                >
                  <span className="block truncate text-sm text-fg">{s.title}</span>
                  <span className="block font-mono text-[10px] text-muted">
                    {s.updated_at.slice(0, 16).replace('T', ' ')}
                    {s.msg_count ? ` · ${s.msg_count}` : ''}
                  </span>
                </button>
                <button
                  onClick={() => {
                    setEditingId(s.id)
                    setDraft(s.title)
                  }}
                  aria-label={t('rename')}
                  title={t('rename')}
                  className="st-session-rename shrink-0 rounded px-1 font-mono text-xs text-muted opacity-0 transition hover:text-ink group-hover:opacity-100"
                >
                  ✎
                </button>
                <button
                  onClick={() => onDelete(s.id)}
                  aria-label={t('delete')}
                  title={t('delete')}
                  className="st-session-delete shrink-0 rounded px-1 font-mono text-xs text-muted opacity-0 transition hover:text-accent group-hover:opacity-100"
                >
                  ✕
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
