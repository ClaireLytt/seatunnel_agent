import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runCompare, type CompareResponse } from '@/api'

const DEMO_RT = `dt,channel,order_cnt,gmv
2026-10-30,app,980,97500.0
2026-10-30,web,410,40200.0
2026-10-30,mini,300,29000.0
2026-10-29,app,1010,100800.0`

const DEMO_OFF = `dt,channel,order_cnt,gmv
2026-10-30,app,1000,100000.0
2026-10-30,web,420,41000.0
2026-10-30,mini,305,29500.0
2026-10-29,app,1020,101000.0
2026-10-29,mini,280,27000.0`

export default function App() {
  const { t, i18n } = useTranslation()
  const [realtime, setRealtime] = useState(DEMO_RT)
  const [offline, setOffline] = useState(DEMO_OFF)
  const [keys, setKeys] = useState('dt,channel')
  const [tolerance, setTolerance] = useState('1')
  const [llm, setLlm] = useState(false)
  const runner = useRunner(
    (rt: string, off: string, k: string, tol: number, lang: string, useLlm: boolean) =>
      runCompare(rt, off, k, tol, lang, useLlm),
  )

  const run = () => {
    if (!realtime.trim() || !offline.trim() || !keys.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(
      realtime,
      offline,
      keys.trim(),
      Math.max(0, parseFloat(tolerance) || 1),
      i18n.language,
      llm,
    )
  }

  const clear = () => {
    setRealtime(DEMO_RT)
    setOffline(DEMO_OFF)
    setKeys('dt,channel')
    setTolerance('1')
    runner.reset()
  }

  const result = runner.result as CompareResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const area =
    'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'
  const input =
    'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / rtoffline" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={label}>{t('rt_label')}</label>
            <textarea
              value={realtime}
              onChange={(e) => setRealtime(e.target.value)}
              placeholder={t('data_ph')}
              rows={6}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('off_label')}</label>
            <textarea
              value={offline}
              onChange={(e) => setOffline(e.target.value)}
              placeholder={t('data_ph')}
              rows={6}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('keys_label')}</label>
            <input
              value={keys}
              onChange={(e) => setKeys(e.target.value)}
              placeholder={t('keys_ph')}
              spellCheck={false}
              className={input}
            />
            <label className={`${label} mt-3`}>{t('tol_label')}</label>
            <input
              value={tolerance}
              onChange={(e) => setTolerance(e.target.value.replace(/[^\d.]/g, ''))}
              inputMode="decimal"
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
