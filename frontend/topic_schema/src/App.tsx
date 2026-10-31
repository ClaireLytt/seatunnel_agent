import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runDiff, type DiffResponse } from '@/api'

const DEMO_OLD = `{
  "type": "record",
  "name": "Order",
  "fields": [
    {"name": "id", "type": "long"},
    {"name": "amount", "type": "int"},
    {"name": "note", "type": ["null", "string"], "default": null},
    {"name": "legacy", "type": "string"}
  ]
}`

const DEMO_NEW = `{
  "type": "record",
  "name": "Order",
  "fields": [
    {"name": "id", "type": "long"},
    {"name": "amount", "type": "double"},
    {"name": "status", "type": "string"},
    {"name": "tag", "type": ["null", "string"], "default": null}
  ]
}`

export default function App() {
  const { t, i18n } = useTranslation()
  const [oldSchema, setOldSchema] = useState(DEMO_OLD)
  const [newSchema, setNewSchema] = useState(DEMO_NEW)
  const [mode, setMode] = useState('backward')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((a: string, b: string, m: string, lang: string, useLlm: boolean) =>
    runDiff(a, b, m, lang, useLlm),
  )

  const run = () => {
    if (!oldSchema.trim() || !newSchema.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(oldSchema, newSchema, mode.trim() || 'backward', i18n.language, llm)
  }

  const clear = () => {
    setOldSchema(DEMO_OLD)
    setNewSchema(DEMO_NEW)
    setMode('backward')
    runner.reset()
  }

  const result = runner.result as DiffResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const area =
    'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / topicschema" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[460px]">
          <Card>
            <label className={label}>{t('old_label')}</label>
            <textarea
              value={oldSchema}
              onChange={(e) => setOldSchema(e.target.value)}
              placeholder={t('schema_ph')}
              rows={9}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('new_label')}</label>
            <textarea
              value={newSchema}
              onChange={(e) => setNewSchema(e.target.value)}
              placeholder={t('schema_ph')}
              rows={9}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('mode_label')}</label>
            <input
              value={mode}
              onChange={(e) => setMode(e.target.value)}
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
