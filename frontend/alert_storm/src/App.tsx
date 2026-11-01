import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runDigest, type DigestResponse } from '@/api'

const DEMO_EXPORT = `[
  {"ts": "2026-10-31 02:10:00", "source": "scheduler",
   "title": "task dwd_orders failed: FileNotFoundException partition dt=2026-10-30", "level": "error"},
  {"ts": "2026-10-31 02:10:30", "source": "scheduler",
   "title": "task dws_orders_daily failed: FileNotFoundException partition dt=2026-10-30", "level": "error"},
  {"ts": "2026-10-31 02:11:00", "source": "scheduler",
   "title": "task ads_board_kpi failed: FileNotFoundException partition dt=2026-10-30", "level": "error"},
  {"ts": "2026-10-31 03:00:00", "source": "kafka",
   "title": "consumer lag over 100000 on group g-orders", "level": "warn"},
  {"ts": "2026-10-31 03:10:00", "source": "kafka",
   "title": "consumer lag over 150000 on group g-orders", "level": "warn"},
  {"ts": "2026-10-31 03:20:00", "source": "kafka",
   "title": "consumer lag over 200000 on group g-orders", "level": "error"}
]`

export default function App() {
  const { t, i18n } = useTranslation()
  const [exportText, setExportText] = useState(DEMO_EXPORT)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((text: string, lang: string, useLlm: boolean) =>
    runDigest(text, lang, useLlm),
  )

  const run = () => {
    if (!exportText.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(exportText, i18n.language, llm)
  }

  const clear = () => {
    setExportText(DEMO_EXPORT)
    runner.reset()
  }

  const result = runner.result as DigestResponse | null

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / alertstorm" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('export_label')}
            </label>
            <textarea
              value={exportText}
              onChange={(e) => setExportText(e.target.value)}
              placeholder={t('export_ph')}
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
