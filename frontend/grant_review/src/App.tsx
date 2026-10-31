import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runReview, type ReviewResponse } from '@/api'

const DEMO_APPLICATIONS = `[
  {"applicant": "zhang3", "role": "analyst",
   "purpose": "月度经营分析看板，需要城市维度的订单金额",
   "tables": [{"table": "dws.orders_daily",
               "columns": ["order_date", "gmv", "order_cnt"]}],
   "duration_days": 30, "write": false},
  {"applicant": "li4", "role": "analyst", "purpose": "排查",
   "tables": [{"table": "dwd.users", "columns": ["*"]}],
   "duration_days": 0, "write": true},
  {"applicant": "wang5", "role": "ops",
   "purpose": "客服回访需要联系方式核对订单",
   "tables": [{"table": "dwd.users",
               "columns": ["user_id", "phone", "id_card"]}],
   "duration_days": 120, "write": false}
]`

export default function App() {
  const { t, i18n } = useTranslation()
  const [application, setApplication] = useState(DEMO_APPLICATIONS)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((text: string, lang: string, useLlm: boolean) =>
    runReview(text, lang, useLlm),
  )

  const run = () => {
    if (!application.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(application, i18n.language, llm)
  }

  const clear = () => {
    setApplication(DEMO_APPLICATIONS)
    runner.reset()
  }

  const result = runner.result as ReviewResponse | null

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / grantreview" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('application_label')}
            </label>
            <textarea
              value={application}
              onChange={(e) => setApplication(e.target.value)}
              placeholder={t('application_ph')}
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
