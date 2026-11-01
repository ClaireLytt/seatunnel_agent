import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runCompare, type CompareResponse } from '@/api'

const DEMO_BASELINE = `order_id,channel,amount,coupon
1,app,100.0,
2,app,110.0,c10
3,web,95.0,
4,app,105.0,
5,web,98.0,c10
6,app,102.0,
7,web,99.0,
8,app,108.0,c10`

const DEMO_CURRENT = `order_id,channel,amount,discount
1,mini,210.0,
2,app,205.0,
3,mini,190.0,
4,mini,220.0,
5,app,,
6,mini,215.0,
7,mini,,
8,app,195.0`

export default function App() {
  const { t, i18n } = useTranslation()
  const [baseline, setBaseline] = useState(DEMO_BASELINE)
  const [current, setCurrent] = useState(DEMO_CURRENT)
  const [maxRows, setMaxRows] = useState('2000')
  const [llm, setLlm] = useState(false)
  const runner = useRunner(
    (base: string, cur: string, cap: number, lang: string, useLlm: boolean) =>
      runCompare(base, cur, cap, lang, useLlm),
  )

  const run = () => {
    if (!baseline.trim() || !current.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(
      baseline,
      current,
      Math.max(1, parseInt(maxRows, 10) || 2000),
      i18n.language,
      llm,
    )
  }

  const clear = () => {
    setBaseline(DEMO_BASELINE)
    setCurrent(DEMO_CURRENT)
    setMaxRows('2000')
    runner.reset()
  }

  const result = runner.result as CompareResponse | null
  const area =
    'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / distanomaly" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={label}>{t('baseline_label')}</label>
            <textarea
              value={baseline}
              onChange={(e) => setBaseline(e.target.value)}
              placeholder={t('data_ph')}
              rows={8}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('current_label')}</label>
            <textarea
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              placeholder={t('data_ph')}
              rows={8}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('maxrows_label')}</label>
            <input
              value={maxRows}
              onChange={(e) => setMaxRows(e.target.value.replace(/[^\d]/g, ''))}
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
