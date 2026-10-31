import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runAnalyze, type AnalyzeResponse } from '@/api'

const DEMO_SERIES = `date,metric,value
2026-10-01,order_cnt,1020
2026-10-02,order_cnt,1015
2026-10-03,order_cnt,1030
2026-10-04,order_cnt,1008
2026-10-05,order_cnt,1025
2026-10-06,order_cnt,1018
2026-10-07,order_cnt,2300
2026-10-08,order_cnt,1022
2026-10-10,order_cnt,1012
2026-10-01,gmv,98000
2026-10-02,gmv,97500
2026-10-03,gmv,99000
2026-10-04,gmv,98200
2026-10-05,gmv,52000
2026-10-06,gmv,51800
2026-10-07,gmv,52100`

export default function App() {
  const { t, i18n } = useTranslation()
  const [series, setSeries] = useState(DEMO_SERIES)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((text: string, lang: string, useLlm: boolean) =>
    runAnalyze(text, lang, useLlm),
  )

  const run = () => {
    if (!series.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(series, i18n.language, llm)
  }

  const clear = () => {
    setSeries(DEMO_SERIES)
    runner.reset()
  }

  const result = runner.result as AnalyzeResponse | null

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / datavolatility" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('series_label')}
            </label>
            <textarea
              value={series}
              onChange={(e) => setSeries(e.target.value)}
              placeholder={t('series_ph')}
              rows={16}
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
