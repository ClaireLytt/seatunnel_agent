import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runPlan, type PlanResponse } from '@/api'

const DEMO_DATA = `event_id,user_id,action,amount,source,created_at
e001,u001,pay,100.0,app,2026-10-01 10:00:00
e002,u002,pay,59.0,app,2026-10-01 10:05:00
e002,u002,pay,59.0,app,2026-10-01 10:05:00
e003,u003,pay,88.0,web,2026-10-01 10:10:00
e003,u003,pay,88.0,gateway,2026-10-01 10:10:02
e004,u004,refund,,app,2026-10-01 10:20:00
e005,u001,pay,"1,100.0",app,2026-10-01 10:25:00
e006,u005,pay,45.0,web ,2026-10-01 10:30:00`

export default function App() {
  const { t, i18n } = useTranslation()
  const [data, setData] = useState(DEMO_DATA)
  const [table, setTable] = useState('dwd.pay_events')
  const [pk, setPk] = useState('event_id')
  const [bizKey, setBizKey] = useState('')
  const [llm, setLlm] = useState(false)
  const runner = useRunner(
    (text: string, tbl: string, pkCols: string, bizCols: string, lang: string, useLlm: boolean) =>
      runPlan(text, tbl, pkCols, bizCols, lang, useLlm),
  )

  const run = () => {
    if (!data.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(data, table, pk, bizKey, i18n.language, llm)
  }

  const clear = () => {
    setData(DEMO_DATA)
    setTable('dwd.pay_events')
    setPk('event_id')
    setBizKey('')
    runner.reset()
  }

  const result = runner.result as PlanResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const input =
    'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / datarepair" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
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
            <label className={`${label} mt-3`}>{t('table_label')}</label>
            <input
              value={table}
              onChange={(e) => setTable(e.target.value)}
              placeholder={t('table_ph')}
              spellCheck={false}
              className={input}
            />
            <label className={`${label} mt-3`}>{t('pk_label')}</label>
            <input
              value={pk}
              onChange={(e) => setPk(e.target.value)}
              placeholder={t('pk_ph')}
              spellCheck={false}
              className={input}
            />
            <label className={`${label} mt-3`}>{t('biz_label')}</label>
            <input
              value={bizKey}
              onChange={(e) => setBizKey(e.target.value)}
              placeholder={t('biz_ph')}
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
