import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runAttribute, type AttributeResponse } from '@/api'

const DEMO_BASE = `dt,channel,region,gmv
2026-10-29,app,north,50000
2026-10-29,app,south,48000
2026-10-29,web,north,21000
2026-10-29,web,south,20000
2026-10-29,mini,north,6000
2026-10-29,mini,south,5000`

const DEMO_CUR = `dt,channel,region,gmv
2026-10-30,app,north,35000
2026-10-30,app,south,47500
2026-10-30,web,north,21500
2026-10-30,web,south,20500
2026-10-30,mini,north,7000
2026-10-30,mini,south,5500`

export default function App() {
  const { t, i18n } = useTranslation()
  const [baseline, setBaseline] = useState(DEMO_BASE)
  const [current, setCurrent] = useState(DEMO_CUR)
  const [dims, setDims] = useState('channel,region')
  const [metric, setMetric] = useState('gmv')
  const [llm, setLlm] = useState(false)
  const runner = useRunner(
    (b: string, c: string, d: string, m: string, lang: string, useLlm: boolean) =>
      runAttribute(b, c, d, m, lang, useLlm),
  )

  const run = () => {
    if (!baseline.trim() || !current.trim() || !dims.trim() || !metric.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(baseline, current, dims.trim(), metric.trim(), i18n.language, llm)
  }

  const clear = () => {
    setBaseline(DEMO_BASE)
    setCurrent(DEMO_CUR)
    setDims('channel,region')
    setMetric('gmv')
    runner.reset()
  }

  const result = runner.result as AttributeResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const area =
    'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'
  const input =
    'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / metricattribution" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={label}>{t('baseline_label')}</label>
            <textarea
              value={baseline}
              onChange={(e) => setBaseline(e.target.value)}
              placeholder={t('data_ph')}
              rows={7}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('current_label')}</label>
            <textarea
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              placeholder={t('data_ph')}
              rows={7}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('dims_label')}</label>
            <input
              value={dims}
              onChange={(e) => setDims(e.target.value)}
              placeholder={t('dims_ph')}
              spellCheck={false}
              className={input}
            />
            <label className={`${label} mt-3`}>{t('metric_label')}</label>
            <input
              value={metric}
              onChange={(e) => setMetric(e.target.value)}
              placeholder={t('metric_ph')}
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
