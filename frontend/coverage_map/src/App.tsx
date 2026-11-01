import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runMap, type MapResponse } from '@/api'

const DEMO_DDL = `CREATE TABLE dwd.orders (
  order_id BIGINT COMMENT '订单ID',
  user_id  BIGINT COMMENT '用户ID',
  amount   DECIMAL(16,2) COMMENT '金额'
) PARTITIONED BY (dt STRING) STORED AS ORC;

CREATE TABLE dws.orders_daily (
  order_date STRING COMMENT '日期',
  gmv        DECIMAL(18,2) COMMENT 'GMV'
) PARTITIONED BY (dt STRING) STORED AS ORC;

CREATE TABLE dim.users (
  user_id   BIGINT COMMENT '用户ID',
  user_name STRING COMMENT '姓名'
) STORED AS ORC;`

const DEMO_RULES = `version: 1
rules:
  - table: dwd.orders
    checks:
      - type: row_count
        min: 1
        max_change_pct: 50
      - type: unique
        columns: [order_id]`

const DEMO_CONTRACT = `tables:
  - name: dim.users
    columns:
      - name: user_id
        type: bigint`

export default function App() {
  const { t, i18n } = useTranslation()
  const [ddl, setDdl] = useState(DEMO_DDL)
  const [rules, setRules] = useState(DEMO_RULES)
  const [contract, setContract] = useState(DEMO_CONTRACT)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((a: string, b: string, c: string, lang: string, useLlm: boolean) =>
    runMap(a, b, c, lang, useLlm),
  )

  const run = () => {
    if (!ddl.trim() || (!rules.trim() && !contract.trim())) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(ddl, rules, contract, i18n.language, llm)
  }

  const clear = () => {
    setDdl(DEMO_DDL)
    setRules(DEMO_RULES)
    setContract(DEMO_CONTRACT)
    runner.reset()
  }

  const result = runner.result as MapResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const area =
    'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / coveragemap" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[460px]">
          <Card>
            <label className={label}>{t('ddl_label')}</label>
            <textarea
              value={ddl}
              onChange={(e) => setDdl(e.target.value)}
              placeholder={t('ddl_ph')}
              rows={8}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('rules_label')}</label>
            <textarea
              value={rules}
              onChange={(e) => setRules(e.target.value)}
              placeholder={t('rules_ph')}
              rows={6}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('contract_label')}</label>
            <textarea
              value={contract}
              onChange={(e) => setContract(e.target.value)}
              placeholder={t('contract_ph')}
              rows={4}
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
