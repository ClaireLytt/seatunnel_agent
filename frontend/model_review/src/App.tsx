import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runReview, type ReviewResponse } from '@/api'

const DEMO_DDL = `CREATE TABLE dim.users (
  user_name  STRING COMMENT '用户姓名',
  city       STRING COMMENT '城市'
) COMMENT '用户维表' STORED AS ORC;

CREATE TABLE dwd.orders (
  order_id    BIGINT COMMENT '订单ID',
  user_id     BIGINT COMMENT '用户ID',
  user_name   STRING COMMENT '用户姓名',
  amount      DECIMAL(16,2) COMMENT '金额'
) COMMENT '订单事实表' STORED AS ORC;

CREATE TABLE dwd.payments (
  pay_id      BIGINT COMMENT '支付ID',
  order_id    BIGINT COMMENT '订单ID',
  user_name   STRING COMMENT '用户姓名',
  pay_amount  DECIMAL(16,2) COMMENT '支付金额'
) PARTITIONED BY (dt STRING) STORED AS ORC;

CREATE TABLE dws.user_profile_tags (
  user_id   BIGINT COMMENT '用户ID',
  tag_a     STRING COMMENT '标签A'
) PARTITIONED BY (dt STRING) STORED AS ORC;`

export default function App() {
  const { t, i18n } = useTranslation()
  const [sql, setSql] = useState(DEMO_DDL)
  const [wideLimit, setWideLimit] = useState('50')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((q: string, w: number, lang: string, useLlm: boolean) =>
    runReview(q, w, lang, useLlm),
  )

  const run = () => {
    if (!sql.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    const w = Math.max(1, parseInt(wideLimit, 10) || 50)
    void runner.run(sql, w, i18n.language, llm)
  }

  const clear = () => {
    setSql(DEMO_DDL)
    setWideLimit('50')
    runner.reset()
  }

  const result = runner.result as ReviewResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / modelreview" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[440px]">
          <Card>
            <label className={label}>{t('sql_label')}</label>
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              placeholder={t('sql_ph')}
              rows={16}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className={`${label} mt-3`}>{t('wide_label')}</label>
            <input
              value={wideLimit}
              onChange={(e) => setWideLimit(e.target.value)}
              inputMode="numeric"
              spellCheck={false}
              className="w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink"
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
