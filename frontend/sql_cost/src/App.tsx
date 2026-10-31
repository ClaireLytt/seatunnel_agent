import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { ApiError, runEstimate } from '@/api'

export default function App() {
  const { t, i18n } = useTranslation()
  const [sql, setSql] = useState(
    "SELECT u.region, SUM(o.amount)\nFROM ods.orders o\nJOIN ods.users u ON o.user_id = u.user_id\nWHERE o.dt = '2024-05-01'\nGROUP BY u.region",
  )
  const [statsFile, setStatsFile] = useState('examples/sqlcost_demo/stats.json')
  const [statsText, setStatsText] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const handed = sessionStorage.getItem('seatunnel.handoff.sqlcost')
    if (!handed) return
    sessionStorage.removeItem('seatunnel.handoff.sqlcost')
    setSql(handed)
  }, [])

  const [error, setError] = useState('')
  const [report, setReport] = useState('')

  const run = async () => {
    if (!sql.trim() || (!statsFile.trim() && !statsText.trim())) {
      setError(t('empty_input'))
      setReport('')
      return
    }
    setBusy(true)
    setError('')
    try {
      const res = await runEstimate(
        sql,
        statsText.trim() ? null : statsFile.trim(),
        statsText,
        i18n.language,
      )
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
      if (e instanceof ApiError && e.code === 'bad_dir') {
        setError(t('bad_dir') + e.path)
      } else {
        setError(String(e))
      }
    } finally {
      setBusy(false)
    }
  }

  const clear = () => {
    setSql('')
    setStatsFile('examples/sqlcost_demo/stats.json')
    setStatsText('')
    setError('')
    setReport('')
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / sqlcost" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('sql_label')}
            </label>
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              placeholder={t('sql_ph')}
              rows={7}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className="mb-2 mt-3 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('stats_label')}
            </label>
            <input
              value={statsFile}
              onChange={(e) => setStatsFile(e.target.value)}
              placeholder={t('stats_ph')}
              spellCheck={false}
              className="w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <button
              onClick={run}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('run_btn')}
            </button>
            <button
              onClick={clear}
              disabled={busy}
              className="mt-2 w-full rounded border-[1.5px] border-transparent px-4 py-2 font-mono text-sm text-ink-soft transition hover:border-line disabled:opacity-50"
            >
              {t('clear_btn')}
            </button>
          </Card>

          <Card>
            <details>
              <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                {t('stats_acc')}
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                <label className="block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                  {t('stats_text_label')}
                </label>
                <textarea
                  value={statsText}
                  onChange={(e) => setStatsText(e.target.value)}
                  placeholder={t('stats_text_ph')}
                  rows={8}
                  spellCheck={false}
                  className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
                />
              </div>
            </details>
          </Card>
        </aside>

        <main className="min-w-0 flex-1">
          <Card>
            {error && (
              <div className="mb-3 font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {error}
              </div>
            )}
            {report && <ReportView markdown={report} />}
            {!report && !error && <p className="text-sm text-muted">{t('report_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
