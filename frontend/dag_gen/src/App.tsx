import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runGenerate, type GenResponse } from '@/api'

const DEMO_SQL = `INSERT INTO dws.orders_daily
SELECT o.order_date, o.user_id, SUM(o.amount) AS gmv
FROM dwd.orders o
JOIN dim.users u ON o.user_id = u.user_id
GROUP BY o.order_date, o.user_id;

INSERT INTO ads.order_counts
SELECT order_date, COUNT(*) AS order_cnt
FROM dwd.orders
GROUP BY order_date;

INSERT INTO ads.final_report
SELECT a.order_date, a.gmv, b.order_cnt
FROM dws.orders_daily a
JOIN ads.order_counts b ON a.order_date = b.order_date;`

export default function App() {
  const { t, i18n } = useTranslation()
  const [sql, setSql] = useState(DEMO_SQL)
  const [dagId, setDagId] = useState('demo_daily')
  const [schedule, setSchedule] = useState('0 2 * * *')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((q: string, d: string, s: string, lang: string, useLlm: boolean) =>
    runGenerate(q, d, s, lang, useLlm),
  )

  const run = () => {
    if (!sql.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(
      sql,
      dagId.trim() || 'pipeline',
      schedule.trim() || '0 2 * * *',
      i18n.language,
      llm,
    )
  }

  const clear = () => {
    setSql(DEMO_SQL)
    setDagId('demo_daily')
    setSchedule('0 2 * * *')
    runner.reset()
  }

  const result = runner.result as GenResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const input =
    'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / daggen" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[440px]">
          <Card>
            <label className={label}>{t('sql_label')}</label>
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              placeholder={t('sql_ph')}
              rows={13}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <div className="mt-3 flex gap-3">
              <div className="flex-1">
                <label className={label}>{t('dagid_label')}</label>
                <input
                  value={dagId}
                  onChange={(e) => setDagId(e.target.value)}
                  spellCheck={false}
                  className={input}
                />
              </div>
              <div className="flex-1">
                <label className={label}>{t('schedule_label')}</label>
                <input
                  value={schedule}
                  onChange={(e) => setSchedule(e.target.value)}
                  spellCheck={false}
                  className={input}
                />
              </div>
            </div>
            <label className="mt-3 flex cursor-pointer items-center gap-2 font-mono text-[12px] text-ink-soft">
              <input type="checkbox" checked={llm} onChange={(e) => setLlm(e.target.checked)} />
              {t('llm_label')}
            </label>
            <button
              onClick={run}
              disabled={runner.busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {runner.busy ? t('running') : t('run_btn')}
            </button>
            <button
              onClick={clear}
              disabled={runner.busy}
              className="mt-2 w-full rounded border-[1.5px] border-transparent px-4 py-2 font-mono text-sm text-ink-soft transition hover:border-line disabled:opacity-50"
            >
              {t('clear_btn')}
            </button>
          </Card>
        </aside>

        <main className="min-w-0 flex-1">
          <Card>
            {runner.error && (
              <div className="mb-3 font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {runner.error}
              </div>
            )}
            {result?.report && <ReportView markdown={result.report} />}
            {!result?.report && !runner.error && (
              <p className="text-sm text-muted">{t('report_ph')}</p>
            )}
          </Card>
        </main>
      </div>
    </div>
  )
}
