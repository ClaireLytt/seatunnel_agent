import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runAllocate, type AllocateResponse } from '@/api'

const DEMO_DATA = `owner,item,storage_gb,compute_hours
trade,dwd.orders,850,120
trade,dws.orders_daily,120,60
trade,ads.gmv_report,15,30
growth,ods.click_log,2400,40
growth,dws.user_profile,300,25
,tmp.old_backup,2000,0
,tmp.export_2025,450,2
risk,dwd.risk_events,180,80`

export default function App() {
  const { t, i18n } = useTranslation()
  const [data, setData] = useState(DEMO_DATA)
  const [storagePrice, setStoragePrice] = useState('0.02')
  const [computePrice, setComputePrice] = useState('0.5')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((q: string, sp: number, cp: number, lang: string, useLlm: boolean) =>
    runAllocate(q, sp, cp, lang, useLlm),
  )

  const run = () => {
    if (!data.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    const sp = Math.max(0, parseFloat(storagePrice) || 0.02)
    const cp = Math.max(0, parseFloat(computePrice) || 0.5)
    void runner.run(data, sp, cp, i18n.language, llm)
  }

  const clear = () => {
    setData(DEMO_DATA)
    setStoragePrice('0.02')
    setComputePrice('0.5')
    runner.reset()
  }

  const result = runner.result as AllocateResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const input =
    'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / costalloc" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[440px]">
          <Card>
            <label className={label}>{t('data_label')}</label>
            <textarea
              value={data}
              onChange={(e) => setData(e.target.value)}
              placeholder={t('data_ph')}
              rows={11}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <div className="mt-3 flex gap-3">
              <div className="flex-1">
                <label className={label}>{t('storage_label')}</label>
                <input
                  value={storagePrice}
                  onChange={(e) => setStoragePrice(e.target.value)}
                  inputMode="decimal"
                  spellCheck={false}
                  className={input}
                />
              </div>
              <div className="flex-1">
                <label className={label}>{t('compute_label')}</label>
                <input
                  value={computePrice}
                  onChange={(e) => setComputePrice(e.target.value)}
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
