import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runPlan, type PlanResponse } from '@/api'

const DEMO_SQL = `INSERT INTO dwd.orders
SELECT order_id, user_id, CAST(amount AS DOUBLE) AS amount, order_date
FROM ods.orders_raw;

INSERT INTO dws.orders_daily
SELECT o.order_date, o.user_id, SUM(o.amount) AS gmv
FROM dwd.orders o
JOIN dim.users u ON o.user_id = u.user_id
GROUP BY o.order_date, o.user_id;`

export default function App() {
  const { t, i18n } = useTranslation()
  const [sql, setSql] = useState(DEMO_SQL)
  const [table, setTable] = useState('dwd.orders')
  const [parts, setParts] = useState('dt=2026-10-30')
  const [mode, setMode] = useState('snapshot')
  const [snapshot, setSnapshot] = useState('snap_dwd_orders_20261030')
  const [llm, setLlm] = useState(false)
  const runner = useRunner(
    (
      q: string,
      tbl: string,
      ps: string[],
      md: string,
      snap: string,
      lang: string,
      useLlm: boolean,
    ) => runPlan(q, tbl, ps, md, snap, lang, useLlm),
  )

  const run = () => {
    if (!sql.trim() || !table.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    const ps = parts
      .split(',')
      .map((p) => p.trim())
      .filter(Boolean)
    void runner.run(sql, table.trim(), ps, mode.trim() || 'rerun', snapshot, i18n.language, llm)
  }

  const clear = () => {
    setSql(DEMO_SQL)
    setTable('dwd.orders')
    setParts('dt=2026-10-30')
    setMode('snapshot')
    setSnapshot('snap_dwd_orders_20261030')
    runner.reset()
  }

  const result = runner.result as PlanResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const input =
    'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / rollbackplan" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={label}>{t('sql_label')}</label>
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              placeholder={t('sql_ph')}
              rows={8}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className={`${label} mt-3`}>{t('table_label')}</label>
            <input
              value={table}
              onChange={(e) => setTable(e.target.value)}
              placeholder={t('table_ph')}
              spellCheck={false}
              className={input}
            />
            <label className={`${label} mt-3`}>{t('parts_label')}</label>
            <input
              value={parts}
              onChange={(e) => setParts(e.target.value)}
              placeholder={t('parts_ph')}
              spellCheck={false}
              className={input}
            />
            <label className={`${label} mt-3`}>{t('mode_label')}</label>
            <input
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              spellCheck={false}
              className={input}
            />
            <label className={`${label} mt-3`}>{t('snapshot_label')}</label>
            <input
              value={snapshot}
              onChange={(e) => setSnapshot(e.target.value)}
              placeholder={t('snapshot_ph')}
              spellCheck={false}
              className={input}
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
