import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runGenerate, type GenResponse } from '@/api'

const DEMO_DDL = `CREATE TABLE inventory.products (
  product_id BIGINT COMMENT '商品ID',
  name       STRING COMMENT '商品名称',
  price      DECIMAL(10,2) COMMENT '价格',
  updated_at TIMESTAMP COMMENT '更新时间'
) COMMENT '商品表'
STORED AS ORC;`

export default function App() {
  const { t, i18n } = useTranslation()
  const [sql, setSql] = useState(DEMO_DDL)
  const [source, setSource] = useState('MySQL-CDC')
  const [sink, setSink] = useState('Doris')
  const [mode, setMode] = useState('')
  const [llm, setLlm] = useState(false)
  const runner = useRunner(
    (q: string, s: string, k: string, m: string, lang: string, useLlm: boolean) =>
      runGenerate(q, s, k, m, lang, useLlm),
  )

  const run = () => {
    if (!sql.trim() || !source.trim() || !sink.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(sql, source.trim(), sink.trim(), mode, i18n.language, llm)
  }

  const clear = () => {
    setSql(DEMO_DDL)
    setSource('MySQL-CDC')
    setSink('Doris')
    setMode('')
    runner.reset()
  }

  const result = runner.result as GenResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const input =
    'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / seatunnelgen" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[440px]">
          <Card>
            <label className={label}>{t('sql_label')}</label>
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              placeholder={t('sql_ph')}
              rows={9}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <div className="mt-3 flex gap-3">
              <div className="flex-1">
                <label className={label}>{t('source_label')}</label>
                <input
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  placeholder={t('source_ph')}
                  spellCheck={false}
                  className={input}
                />
              </div>
              <div className="flex-1">
                <label className={label}>{t('sink_label')}</label>
                <input
                  value={sink}
                  onChange={(e) => setSink(e.target.value)}
                  placeholder={t('sink_ph')}
                  spellCheck={false}
                  className={input}
                />
              </div>
            </div>
            <label className={`${label} mt-3`}>{t('mode_label')}</label>
            <input
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              placeholder={t('mode_ph')}
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
