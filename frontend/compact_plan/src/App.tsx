import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runPlan, type PlanResponse } from '@/api'

const DEMO_DATA = `table,partition,file_count,total_mb
ods.click_log,dt=2026-10-28,1450,2900
ods.click_log,dt=2026-10-29,1280,2560
ods.click_log,dt=2026-10-30,960,1920
dwd.orders,dt=2026-10-29,48,96
dwd.orders,dt=2026-10-30,52,110
dws.orders_daily,dt=2026-10-30,8,420
dim.users,dt=2026-10-30,4,18`

export default function App() {
  const { t, i18n } = useTranslation()
  const [data, setData] = useState(DEMO_DATA)
  const [smallMb, setSmallMb] = useState('32')
  const [targetMb, setTargetMb] = useState('256')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((q: string, s: number, tg: number, lang: string, useLlm: boolean) =>
    runPlan(q, s, tg, lang, useLlm),
  )

  const run = () => {
    if (!data.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    const s = Math.max(1, parseFloat(smallMb) || 32)
    const tg = Math.max(s + 1, parseFloat(targetMb) || 256)
    void runner.run(data, s, tg, i18n.language, llm)
  }

  const clear = () => {
    setData(DEMO_DATA)
    setSmallMb('32')
    setTargetMb('256')
    runner.reset()
  }

  const result = runner.result as PlanResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const input =
    'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / compactplan" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[440px]">
          <Card>
            <label className={label}>{t('data_label')}</label>
            <textarea
              value={data}
              onChange={(e) => setData(e.target.value)}
              placeholder={t('data_ph')}
              rows={10}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <div className="mt-3 flex gap-3">
              <div className="flex-1">
                <label className={label}>{t('small_label')}</label>
                <input
                  value={smallMb}
                  onChange={(e) => setSmallMb(e.target.value)}
                  inputMode="decimal"
                  spellCheck={false}
                  className={input}
                />
              </div>
              <div className="flex-1">
                <label className={label}>{t('target_label')}</label>
                <input
                  value={targetMb}
                  onChange={(e) => setTargetMb(e.target.value)}
                  inputMode="decimal"
                  spellCheck={false}
                  className={input}
                />
              </div>
            </div>
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
