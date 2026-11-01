import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runAdvise, type AdviseResponse } from '@/api'

const DEMO_DATA = `table,partition,size_gb,last_access
dwd.orders,dt=2026-10-29,12.5,2026-10-30
dwd.orders,dt=2026-10-01,12.1,2026-10-28
dwd.orders,dt=2026-08-15,11.8,2026-10-05
dwd.orders,dt=2026-04-10,11.2,2026-05-01
dwd.orders,dt=2026-01-05,10.9,
dwd.orders,dt=2025-11-20,10.4,
ods.click_log,dt=2026-10-30,80.0,2026-10-30
ods.click_log,dt=2026-07-01,78.5,
ods.click_log,dt=2026-03-15,75.0,
ods.click_log,dt=2025-12-01,70.2,
dim.users,dt=2026-10-30,2.1,2026-10-30
dim.users,dt=2026-10-29,2.1,2026-10-29`

export default function App() {
  const { t, i18n } = useTranslation()
  const [data, setData] = useState(DEMO_DATA)
  const [activeDays, setActiveDays] = useState('90')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((q: string, a: number, lang: string, useLlm: boolean) =>
    runAdvise(q, a, lang, useLlm),
  )

  const run = () => {
    if (!data.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    const a = Math.max(1, parseInt(activeDays, 10) || 90)
    void runner.run(data, a, i18n.language, llm)
  }

  const clear = () => {
    setData(DEMO_DATA)
    setActiveDays('90')
    runner.reset()
  }

  const result = runner.result as AdviseResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / retention" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[440px]">
          <Card>
            <label className={label}>{t('data_label')}</label>
            <textarea
              value={data}
              onChange={(e) => setData(e.target.value)}
              placeholder={t('data_ph')}
              rows={14}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className={`${label} mt-3`}>{t('active_label')}</label>
            <input
              value={activeDays}
              onChange={(e) => setActiveDays(e.target.value)}
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
