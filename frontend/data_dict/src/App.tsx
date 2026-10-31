import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runGenerate, type GenerateResponse } from '@/api'

const DEMO_CATALOG = `[
  {"table": "dws.orders_daily", "comment": "订单日汇总",
   "columns": [{"name": "order_date", "comment": "订单日期"},
               {"name": "user_id", "comment": ""},
               {"name": "order_cnt", "comment": "订单量"},
               {"name": "gmv", "comment": ""}]},
  {"table": "dim.users", "comment": "用户维表",
   "columns": [{"name": "user_id", "comment": "用户ID"},
               {"name": "city", "comment": ""},
               {"name": "register_date", "comment": "注册日期"}]}
]`

const DEMO_SQL = `SELECT user_id, SUM(gmv) FROM dws.orders_daily
WHERE order_date >= date_sub(current_date, 7) GROUP BY user_id;`

export default function App() {
  const { t, i18n } = useTranslation()
  const [catalog, setCatalog] = useState(DEMO_CATALOG)
  const [sql, setSql] = useState(DEMO_SQL)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((cat: string, q: string, lang: string, useLlm: boolean) =>
    runGenerate(cat, q, lang, useLlm),
  )

  const run = () => {
    if (!catalog.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(catalog, sql, i18n.language, llm)
  }

  const clear = () => {
    setCatalog(DEMO_CATALOG)
    setSql(DEMO_SQL)
    runner.reset()
  }

  const result = runner.result as GenerateResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / datadict" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={label}>{t('catalog_label')}</label>
            <textarea
              value={catalog}
              onChange={(e) => setCatalog(e.target.value)}
              placeholder={t('catalog_ph')}
              rows={12}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className={`${label} mt-3`}>{t('sql_label')}</label>
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              placeholder={t('sql_ph')}
              rows={5}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
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
