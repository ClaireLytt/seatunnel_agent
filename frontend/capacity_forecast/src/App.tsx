import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runForecast, type ForecastResponse } from '@/api'

const DEMO_SERIES = `date,metric,value
2026-10-24,ods.click_log,620
2026-10-25,ods.click_log,640
2026-10-26,ods.click_log,660
2026-10-27,ods.click_log,680
2026-10-28,ods.click_log,700
2026-10-29,ods.click_log,720
2026-10-30,ods.click_log,740
2026-10-24,dwd.orders,214
2026-10-25,dwd.orders,216
2026-10-26,dwd.orders,218
2026-10-27,dwd.orders,220
2026-10-28,dwd.orders,222
2026-10-29,dwd.orders,224
2026-10-30,dwd.orders,226`

export default function App() {
  const { t, i18n } = useTranslation()
  const [series, setSeries] = useState(DEMO_SERIES)
  const [quota, setQuota] = useState('2000')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((text: string, q: number, lang: string, useLlm: boolean) =>
    runForecast(text, q, lang, useLlm),
  )

  const run = () => {
    const q = parseFloat(quota)
    if (!series.trim() || !(q > 0)) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(series, q, i18n.language, llm)
  }

  const clear = () => {
    setSeries(DEMO_SERIES)
    setQuota('2000')
    runner.reset()
  }

  const result = runner.result as ForecastResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / capacityforecast" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={label}>{t('series_label')}</label>
            <textarea
              value={series}
              onChange={(e) => setSeries(e.target.value)}
              placeholder={t('series_ph')}
              rows={14}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className={`${label} mt-3`}>{t('quota_label')}</label>
            <input
              value={quota}
              onChange={(e) => setQuota(e.target.value.replace(/[^\d.]/g, ''))}
              inputMode="decimal"
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
