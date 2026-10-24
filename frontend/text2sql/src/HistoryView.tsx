import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import {
  clearQlog,
  deleteQlog,
  fetchQlog,
  fetchSavedSessions,
  qlogExportUrl,
  resumeSaved,
  type QlogRecord,
  type SavedSession,
  type SessionMeta,
} from '@/api'

/** The #history view: query log with detail/delete/clear/export, plus
 *  saved chat sessions with resume-into-chat. */
export function HistoryView({
  session,
  onResume,
}: {
  session: SessionMeta | null
  onResume: (title: string, chat: { role: string; content: string }[]) => void
}) {
  const { t } = useTranslation()
  const [records, setRecords] = useState<QlogRecord[]>([])
  const [sel, setSel] = useState<number | null>(null)
  const [saved, setSaved] = useState<SavedSession[]>([])
  const [err, setErr] = useState('')

  const refresh = () => {
    fetchQlog().then((r) => {
      setRecords(r.records)
      setSel(null)
    })
    fetchSavedSessions().then((r) => setSaved(r.sessions))
  }
  useEffect(refresh, [])

  const resume = async (id: string) => {
    if (!session) {
      setErr(t('resumeNeedsConnect'))
      return
    }
    try {
      const r = await resumeSaved(session.session_id, id)
      onResume(r.title, r.chat)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="st-history-view space-y-4">
      <Card>
        <div className="mb-2 flex items-center gap-3 font-mono text-[12px]">
          <span className="uppercase tracking-[0.18em] text-ink-soft">{t('queryLog')}</span>
          <button onClick={refresh} className="rounded border border-line px-2 text-muted">
            ⟳
          </button>
          <a
            href={qlogExportUrl}
            download="qlog.csv"
            className="rounded border border-ink px-2 text-ink"
          >
            CSV
          </a>
          <button
            onClick={() => sel !== null && deleteQlog([sel]).then(refresh)}
            disabled={sel === null}
            className="rounded border border-line px-2 text-muted disabled:opacity-40"
          >
            {t('deleteSel')}
          </button>
          <button
            onClick={() => clearQlog().then(refresh)}
            className="rounded border border-accent px-2 text-accent"
          >
            {t('clearAllLog')}
          </button>
        </div>
        <table className="w-full font-mono text-[13px]">
          <thead>
            <tr className="border-b-2 border-ink text-left">
              <th className="px-2 py-1 text-ink">{t('time')}</th>
              <th className="px-2 py-1 text-ink">{t('question')}</th>
              <th className="px-2 py-1 text-ink">{t('status')}</th>
              <th className="px-2 py-1 text-ink">ms</th>
            </tr>
          </thead>
          <tbody>
            {records.map((r, i) => (
              <tr
                key={i}
                onClick={() => setSel(i)}
                className={
                  'cursor-pointer border-b border-line last:border-b-0 ' +
                  (sel === i ? 'bg-paper' : '')
                }
              >
                <td className="px-2 py-1 text-muted">{r.timestamp?.slice(5, 19)}</td>
                <td className="px-2 py-1 text-fg">{r.user_query?.trim() || '—'}</td>
                <td
                  className="px-2 py-1"
                  style={{ color: r.status === 'ok' ? 'var(--ok)' : 'var(--accent)' }}
                >
                  {r.status}
                </td>
                <td className="px-2 py-1 text-muted">{r.exec_time_ms ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {sel !== null && records[sel] && (
          <pre className="st-qlog-detail mt-2 overflow-x-auto rounded border border-line bg-paper px-2 py-1 font-mono text-[12px] text-fg">
            {records[sel].generated_sql}
          </pre>
        )}
      </Card>

      <Card>
        <div className="mb-2 font-mono text-[12px] uppercase tracking-[0.18em] text-ink-soft">
          {t('savedSessions')}
        </div>
        <div className="space-y-1 font-mono text-[13px]">
          {saved.map((s) => (
            <div key={s.id} className="flex items-center gap-3">
              <span className="text-fg">{s.title}</span>
              <span className="text-muted">{s.updated_at?.slice(0, 16)}</span>
              <button
                onClick={() => resume(s.id)}
                className="st-resume ml-auto rounded border border-ink px-2 text-ink"
              >
                {t('resume')}
              </button>
            </div>
          ))}
          {saved.length === 0 && <span className="text-muted">—</span>}
        </div>
        {err && <div className="mt-2 font-mono text-[12px] text-accent">{err}</div>}
      </Card>
    </div>
  )
}
