import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runAnalyze, type AnalyzeResponse } from '@/api'

const DEMO_EVENTS = `event_id,produce_ts,ingest_ts,process_ts,sink_ts
e001,2026-10-31 10:00:00.000,2026-10-31 10:00:00.200,2026-10-31 10:00:01.100,2026-10-31 10:00:01.400
e002,2026-10-31 10:00:01.000,2026-10-31 10:00:01.180,2026-10-31 10:00:02.050,2026-10-31 10:00:02.300
e003,2026-10-31 10:00:02.000,2026-10-31 10:00:02.250,2026-10-31 10:00:03.200,2026-10-31 10:00:03.500
e004,2026-10-31 10:00:03.000,2026-10-31 10:00:03.190,2026-10-31 10:00:04.000,2026-10-31 10:00:04.260
e005,2026-10-31 10:00:04.000,2026-10-31 10:00:04.210,2026-10-31 10:00:05.100,2026-10-31 10:00:05.350
e006,2026-10-31 10:00:05.000,2026-10-31 10:00:05.230,2026-10-31 10:00:06.000,2026-10-31 10:00:06.280
e007,2026-10-31 10:00:06.000,2026-10-31 10:00:06.200,2026-10-31 10:00:07.050,2026-10-31 10:00:07.300
e008,2026-10-31 10:00:07.000,2026-10-31 10:00:07.220,2026-10-31 10:01:20.000,2026-10-31 10:01:20.400`

export default function App() {
  const { t, i18n } = useTranslation()
  const [events, setEvents] = useState(DEMO_EVENTS)
  const [slaMs, setSlaMs] = useState('2000')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((text: string, sla: number, lang: string, useLlm: boolean) =>
    runAnalyze(text, sla, lang, useLlm),
  )

  const run = () => {
    if (!events.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(events, Math.max(0, parseInt(slaMs, 10) || 0), i18n.language, llm)
  }

  const clear = () => {
    setEvents(DEMO_EVENTS)
    setSlaMs('2000')
    runner.reset()
  }

  const result = runner.result as AnalyzeResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / rtlatency" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={label}>{t('events_label')}</label>
            <textarea
              value={events}
              onChange={(e) => setEvents(e.target.value)}
              placeholder={t('events_ph')}
              rows={14}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className={`${label} mt-3`}>{t('sla_label')}</label>
            <input
              value={slaMs}
              onChange={(e) => setSlaMs(e.target.value.replace(/[^\d]/g, ''))}
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
