import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runAnalyze, type AnalyzeResponse } from '@/api'

const DEMO_DDL = `CREATE TABLE dwd.orders (
  order_id    BIGINT COMMENT '订单ID',
  user_id     BIGINT COMMENT '用户ID',
  amount      DECIMAL(16,2) COMMENT '金额',
  note        STRING COMMENT '备注',
  legacy_flag INT COMMENT '历史标记'
) STORED AS ORC;

CREATE TABLE dim.users (
  user_id   BIGINT COMMENT '用户ID',
  user_name STRING COMMENT '姓名',
  city      STRING COMMENT '城市'
) STORED AS ORC;

CREATE TABLE tmp.old_backup (
  x INT COMMENT '废弃'
) STORED AS ORC;`

const DEMO_QUERIES = `SELECT o.order_id, o.amount FROM dwd.orders o WHERE o.user_id = 1;

SELECT u.user_name, SUM(o.amount) AS gmv
FROM dwd.orders o
JOIN dim.users u ON o.user_id = u.user_id
GROUP BY u.user_name;

SELECT * FROM dwd.orders;

SELECT amount FROM dwd.orders;`

export default function App() {
  const { t, i18n } = useTranslation()
  const [ddl, setDdl] = useState(DEMO_DDL)
  const [queries, setQueries] = useState(DEMO_QUERIES)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((a: string, b: string, lang: string, useLlm: boolean) =>
    runAnalyze(a, b, lang, useLlm),
  )

  const run = () => {
    if (!ddl.trim() || !queries.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(ddl, queries, i18n.language, llm)
  }

  const clear = () => {
    setDdl(DEMO_DDL)
    setQueries(DEMO_QUERIES)
    runner.reset()
  }

  const result = runner.result as AnalyzeResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const area =
    'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / fieldusage" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[460px]">
          <Card>
            <label className={label}>{t('ddl_label')}</label>
            <textarea
              value={ddl}
              onChange={(e) => setDdl(e.target.value)}
              placeholder={t('ddl_ph')}
              rows={10}
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
