import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runCheck, type CheckResponse } from '@/api'

const DEMO_LISTING = `table,partition,size_gb,rows
ods.click_log,dt=2026-10-24,20.1,41000000
ods.click_log,dt=2026-10-25,19.8,40200000
ods.click_log,dt=2026-10-26,20.5,41500000
ods.click_log,dt=2026-10-29,21.0,42000000
ods.click_log,dt=2026-10-30,6.0,12000000
dwd.orders,dt=2026-10-26,8.0,9000000
dwd.orders,dt=2026-10-27,8.2,9100000
dwd.orders,dt=2026-10-28,0,0
dwd.orders,dt=2026-10-29,8.1,9050000
dwd.orders,dt=2026-10-30,95.0,99000000`

export default function App() {
  const { t, i18n } = useTranslation()
  const [listing, setListing] = useState(DEMO_LISTING)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((text: string, lang: string, useLlm: boolean) =>
    runCheck(text, lang, useLlm),
  )

  const run = () => {
    if (!listing.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(listing, i18n.language, llm)
  }

  const clear = () => {
    setListing(DEMO_LISTING)
    runner.reset()
  }

  const result = runner.result as CheckResponse | null

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / partitionhealth" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('listing_label')}
            </label>
            <textarea
              value={listing}
              onChange={(e) => setListing(e.target.value)}
              placeholder={t('listing_ph')}
              rows={14}
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
