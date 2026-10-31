import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runSearch, type SearchResponse } from '@/api'

const DEMO_CATALOG = `[
  {"table": "dws.orders_daily", "comment": "订单日汇总：按日×用户聚合的订单量与金额",
   "columns": [{"name": "order_date", "comment": "订单日期"},
               {"name": "order_cnt", "comment": "订单量"},
               {"name": "gmv", "comment": "成交金额"}]},
  {"table": "dwd.orders", "comment": "订单明细：一单一行",
   "columns": [{"name": "order_id", "comment": "订单号"},
               {"name": "amount", "comment": "订单金额"},
               {"name": "channel", "comment": "下单渠道"}]},
  {"table": "dim.users", "comment": "用户维表",
   "columns": [{"name": "user_id", "comment": "用户ID"},
               {"name": "city", "comment": "常住城市"}]}
]`

export default function App() {
  const { t, i18n } = useTranslation()
  const [catalog, setCatalog] = useState(DEMO_CATALOG)
  const [query, setQuery] = useState('按日的订单金额汇总')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((cat: string, q: string, lang: string, useLlm: boolean) =>
    runSearch(cat, q, lang, useLlm),
  )

  const run = () => {
    if (!catalog.trim() || !query.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(catalog, query.trim(), i18n.language, llm)
  }

  const clear = () => {
    setCatalog(DEMO_CATALOG)
    setQuery('按日的订单金额汇总')
    runner.reset()
  }

  const result = runner.result as SearchResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / assetsearch" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={label}>{t('query_label')}</label>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('query_ph')}
              spellCheck={false}
              className="w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className={`${label} mt-3`}>{t('catalog_label')}</label>
            <textarea
              value={catalog}
              onChange={(e) => setCatalog(e.target.value)}
              placeholder={t('catalog_ph')}
              rows={14}
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
