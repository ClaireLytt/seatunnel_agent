import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runScore, type ScoreResponse } from '@/api'

const DEMO_DATA = `task,date,deadline,finish
dws_orders_daily,2026-10-25,07:00,06:41
dws_orders_daily,2026-10-26,07:00,06:55
dws_orders_daily,2026-10-27,07:00,07:20
dws_orders_daily,2026-10-28,07:00,08:35
dws_orders_daily,2026-10-29,07:00,07:45
dws_orders_daily,2026-10-30,07:00,09:10
ads_user_report,2026-10-25,08:00,07:30
ads_user_report,2026-10-26,08:00,07:42
ads_user_report,2026-10-27,08:00,07:38
ads_user_report,2026-10-28,08:00,08:05
ads_user_report,2026-10-29,08:00,07:50
ads_user_report,2026-10-30,08:00,07:45
dim_users_sync,2026-10-25,02:00,01:30
dim_users_sync,2026-10-26,02:00,01:28
dim_users_sync,2026-10-27,02:00,01:35
dim_users_sync,2026-10-28,02:00,01:31
dim_users_sync,2026-10-29,02:00,01:29
dim_users_sync,2026-10-30,02:00,01:33`

export default function App() {
  const { t, i18n } = useTranslation()
  const [data, setData] = useState(DEMO_DATA)
  const [target, setTarget] = useState('0.95')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((q: string, tg: number, lang: string, useLlm: boolean) =>
    runScore(q, tg, lang, useLlm),
  )

  const run = () => {
    if (!data.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    const tg = Math.min(1, Math.max(0.5, parseFloat(target) || 0.95))
    void runner.run(data, tg, i18n.language, llm)
  }

  const clear = () => {
    setData(DEMO_DATA)
    setTarget('0.95')
    runner.reset()
  }

  const result = runner.result as ScoreResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / slaboard" maxW="max-w-[620px]" />

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
            <label className={`${label} mt-3`}>{t('target_label')}</label>
            <input
              value={target}
              onChange={(e) => setTarget(e.target.value)}
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
