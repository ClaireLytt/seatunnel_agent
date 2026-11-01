import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runPlan, type PlanResponse } from '@/api'

const DEMO_DATA = `order_id,user_id,order_date,status,amount
10001,23,2026-10-01,paid,120.50
10002,41,2026-10-01,paid,80.00
10003,23,2026-10-02,refund,33.20
10004,87,2026-10-03,paid,15.90
10005,41,2026-10-05,paid,220.00
10006,19,2026-10-08,paid,42.75
10007,65,2026-10-12,refund,99.99
10008,23,2026-10-15,paid,7.25
10009,87,2026-10-20,paid,310.40
10010,54,2026-10-28,paid,66.10`

const DEMO_QUERIES = `SELECT SUM(amount) FROM dwd.orders WHERE order_date = '2026-10-30';

SELECT COUNT(*) FROM dwd.orders
WHERE order_date >= '2026-10-01' AND status = 'paid';

SELECT * FROM dwd.orders WHERE user_id = 42;

SELECT amount FROM dwd.orders WHERE order_id = 10042;

SELECT status, COUNT(*) FROM dwd.orders GROUP BY status;`

export default function App() {
  const { t, i18n } = useTranslation()
  const [data, setData] = useState(DEMO_DATA)
  const [queries, setQueries] = useState(DEMO_QUERIES)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((a: string, b: string, lang: string, useLlm: boolean) =>
    runPlan(a, b, lang, useLlm),
  )

  const run = () => {
    if (!data.trim() || !queries.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(data, queries, i18n.language, llm)
  }

  const clear = () => {
    setData(DEMO_DATA)
    setQueries(DEMO_QUERIES)
    runner.reset()
  }

  const result = runner.result as PlanResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const area =
    'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / partitionplan" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[460px]">
          <Card>
            <label className={label}>{t('data_label')}</label>
            <textarea
              value={data}
              onChange={(e) => setData(e.target.value)}
              placeholder={t('data_ph')}
              rows={9}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('queries_label')}</label>
            <textarea
              value={queries}
              onChange={(e) => setQueries(e.target.value)}
              placeholder={t('queries_ph')}
              rows={9}
              spellCheck={false}
              className={area}
            />
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
