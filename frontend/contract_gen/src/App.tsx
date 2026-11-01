import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runGenerate, type GenResponse } from '@/api'

const DEMO_DDL = `CREATE TABLE ods.user_info (
  user_id   BIGINT COMMENT '用户ID',
  user_name STRING COMMENT '用户姓名',
  amount    DECIMAL(16,2) COMMENT '累计消费'
) COMMENT '用户基础信息表'
PARTITIONED BY (dt STRING COMMENT '分区日期')
STORED AS ORC;

CREATE TABLE stg.clickstream_raw (
  event_id  BIGINT,
  user_id   BIGINT,
  event_ts  TIMESTAMP COMMENT '事件时间',
  payload   STRING
) PARTITIONED BY (dt STRING)
STORED AS ORC;`

export default function App() {
  const { t, i18n } = useTranslation()
  const [sql, setSql] = useState(DEMO_DDL)
  const [tables, setTables] = useState('')
  const [withTypes, setWithTypes] = useState(true)
  const [strict, setStrict] = useState(false)
  const [llm, setLlm] = useState(false)
  const runner = useRunner(
    (q: string, ts: string[], wt: boolean, st: boolean, lang: string, useLlm: boolean) =>
      runGenerate(q, ts, wt, st, lang, useLlm),
  )

  const run = () => {
    if (!sql.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    const ts = tables
      .split(',')
      .map((p) => p.trim())
      .filter(Boolean)
    void runner.run(sql, ts, withTypes, strict, i18n.language, llm)
  }

  const clear = () => {
    setSql(DEMO_DDL)
    setTables('')
    setWithTypes(true)
    setStrict(false)
    runner.reset()
  }

  const result = runner.result as GenResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const check = 'mt-3 flex cursor-pointer items-center gap-2 font-mono text-[12px] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / contractgen" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={label}>{t('sql_label')}</label>
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              placeholder={t('sql_ph')}
              rows={12}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className={`${label} mt-3`}>{t('tables_label')}</label>
            <input
              value={tables}
              onChange={(e) => setTables(e.target.value)}
              placeholder={t('tables_ph')}
              spellCheck={false}
              className="w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className={check}>
              <input
                type="checkbox"
                checked={withTypes}
                onChange={(e) => setWithTypes(e.target.checked)}
              />
              {t('types_label')}
            </label>
            <label className={check}>
              <input
                type="checkbox"
                checked={strict}
                onChange={(e) => setStrict(e.target.checked)}
              />
              {t('strict_label')}
            </label>
            <label className={check}>
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
