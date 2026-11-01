import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runConvert, type ConvertResponse } from '@/api'

const DEMO_SCHEMA = `{
  "type": "record",
  "name": "Order",
  "namespace": "shop",
  "fields": [
    {"name": "id", "type": "long", "doc": "订单ID"},
    {"name": "amount",
     "type": {"type": "bytes", "logicalType": "decimal",
              "precision": 16, "scale": 2}},
    {"name": "status",
     "type": {"type": "enum", "name": "Status",
              "symbols": ["paid", "refund"]}},
    {"name": "note", "type": ["null", "string"], "default": null},
    {"name": "tags", "type": {"type": "array", "items": "string"}},
    {"name": "created",
     "type": {"type": "long", "logicalType": "timestamp-millis"}},
    {"name": "mixed", "type": ["int", "string"]}
  ]
}`

export default function App() {
  const { t, i18n } = useTranslation()
  const [schema, setSchema] = useState(DEMO_SCHEMA)
  const [table, setTable] = useState('')
  const [dialect, setDialect] = useState('hive')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((q: string, tbl: string, d: string, lang: string, useLlm: boolean) =>
    runConvert(q, tbl, d, lang, useLlm),
  )

  const run = () => {
    if (!schema.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(schema, table, dialect.trim() || 'hive', i18n.language, llm)
  }

  const clear = () => {
    setSchema(DEMO_SCHEMA)
    setTable('')
    setDialect('hive')
    runner.reset()
  }

  const result = runner.result as ConvertResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const input =
    'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / avro2ddl" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[460px]">
          <Card>
            <label className={label}>{t('schema_label')}</label>
            <textarea
              value={schema}
              onChange={(e) => setSchema(e.target.value)}
              placeholder={t('schema_ph')}
              rows={15}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <div className="mt-3 flex gap-3">
              <div className="flex-[2]">
                <label className={label}>{t('table_label')}</label>
                <input
                  value={table}
                  onChange={(e) => setTable(e.target.value)}
                  placeholder={t('table_ph')}
                  spellCheck={false}
                  className={input}
                />
              </div>
              <div className="flex-1">
                <label className={label}>{t('dialect_label')}</label>
                <input
                  value={dialect}
                  onChange={(e) => setDialect(e.target.value)}
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
