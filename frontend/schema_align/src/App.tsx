import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runAlign, type AlignResponse } from '@/api'

const DEMO_SRC = `CREATE TABLE orders (
  order_id BIGINT NOT NULL,
  user_id BIGINT,
  amount DECIMAL(38,6),
  note VARCHAR(256),
  created_at TIMESTAMP,
  channel VARCHAR(32)
)`

const DEMO_SINK = `CREATE TABLE ods_orders (
  order_id INT NOT NULL,
  amount DECIMAL(18,2),
  note VARCHAR(64),
  created_at DATE,
  channel VARCHAR(64) NOT NULL,
  etl_time TIMESTAMP NOT NULL
)`

export default function App() {
  const { t, i18n } = useTranslation()
  const [source, setSource] = useState(DEMO_SRC)
  const [sink, setSink] = useState(DEMO_SINK)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((s: string, d: string, lang: string, useLlm: boolean) =>
    runAlign(s, d, lang, useLlm),
  )

  const run = () => {
    if (!source.trim() || !sink.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(source, sink, i18n.language, llm)
  }

  const clear = () => {
    setSource(DEMO_SRC)
    setSink(DEMO_SINK)
    runner.reset()
  }

  const result = runner.result as AlignResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const area =
    'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / schemaalign" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={label}>{t('source_label')}</label>
            <textarea
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder={t('ddl_ph')}
              rows={9}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('sink_label')}</label>
            <textarea
              value={sink}
              onChange={(e) => setSink(e.target.value)}
              placeholder={t('ddl_ph')}
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
