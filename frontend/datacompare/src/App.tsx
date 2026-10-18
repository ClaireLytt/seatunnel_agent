import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  createSession,
  fetchMeta,
  OPTIONS_DEFAULTS,
  type CompareOptions,
  type ComparisonTemplate,
  type Meta,
  type PresetConnection,
} from '@/api'
import { ActionRow } from '@/components/ActionRow'
import { ConnectForm, type ConnFields } from '@/components/ConnectForm'
import { GenerationCard } from '@/components/GenerationCard'
import { OptionsCard } from '@/components/OptionsCard'
import { PresetsCard } from '@/components/PresetsCard'
import { TemplatesCard } from '@/components/TemplatesCard'
import { Card } from '@shared/components/card'

export default function App() {
  const { t } = useTranslation()

  const [meta, setMeta] = useState<Meta | null>(null)
  const [sessionId, setSessionId] = useState('')
  const [error, setError] = useState('')
  const [tableA, setTableA] = useState('')
  const [tableB, setTableB] = useState('')
  const [resultHtml, setResultHtml] = useState('')

  // Global comparison options — ride on every action request (tickets 03+).
  const [options, setOptions] = useState<CompareOptions>(OPTIONS_DEFAULTS)
  const [resetSeq, setResetSeq] = useState(0)

  // Current connect-form fields per side (for "save preset from side X");
  // a ref so keystrokes in the forms don't re-render the whole page.
  const fieldsRef = useRef<Record<'a' | 'b', ConnFields>>({
    a: { ds_type: '', host: '', port: '', db: '', username: '', password: '' },
    b: { ds_type: '', host: '', port: '', db: '', username: '', password: '' },
  })
  const [presetA, setPresetA] = useState<{ seq: number; conn: PresetConnection }>()
  const [presetB, setPresetB] = useState<{ seq: number; conn: PresetConnection }>()
  const presetSeq = useRef(0)

  useEffect(() => {
    fetchMeta()
      .then(setMeta)
      .catch((e) => setError(String(e)))
    createSession()
      .then(setSessionId)
      .catch((e) => setError(String(e)))
  }, [])

  const resetOptions = () => {
    setOptions(OPTIONS_DEFAULTS)
    setResetSeq((s) => s + 1)
  }

  const presetFields = (side: 'a' | 'b') => {
    const f = fieldsRef.current[side]
    return {
      ds_type: f.ds_type,
      host: f.host,
      port: Number(f.port) || 0,
      database: f.db,
      username: f.username,
      password: f.password,
    }
  }

  const applyPreset = (side: 'a' | 'b', conn: PresetConnection) => {
    presetSeq.current += 1
    ;(side === 'a' ? setPresetA : setPresetB)({ seq: presetSeq.current, conn })
  }

  // Templates: snapshot and restore of tables + options (fields owned by
  // other feature cards — watermark/quality/webhook — ride along empty
  // until those cards land and wire in).
  const getTemplate = () => ({
    table_a: tableA,
    table_b: tableB,
    where_clause: options.where,
    key_columns: options.key_columns,
    threshold: options.threshold,
    column_mapping: options.column_mapping,
    sample_strategy: options.strategy,
    watermark_column: '',
    quality_rules: '',
    webhook_url: '',
    notify_on_fail: false,
    masking_enabled: options.masking,
  })

  const applyTemplate = (tmpl: ComparisonTemplate) => {
    setTableA(tmpl.table_a)
    setTableB(tmpl.table_b)
    setOptions({
      where: tmpl.where_clause,
      threshold: tmpl.threshold,
      key_columns: tmpl.key_columns,
      column_mapping: tmpl.column_mapping,
      strategy: tmpl.sample_strategy,
      stratified_col: '',
      masking: tmpl.masking_enabled,
    })
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <span className="mb-3 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            data / compare
          </span>
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink">{t('title')}</h1>
          <p className="mt-2 max-w-[620px] text-sm text-muted">{t('subtitle')}</p>
        </div>
        <a
          href="/"
          title={t('home')}
          className="shrink-0 rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
        >
          {t('home')}
        </a>
      </header>

      {error && (
        <div className="mt-4 font-mono text-sm" style={{ color: 'var(--accent)' }}>
          ❌ {error}
        </div>
      )}

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        {/* Wide configuration sidebar */}
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[400px]">
          {meta && (
            <>
              <ConnectForm
                side="a"
                datasources={meta.datasources}
                sessionId={sessionId}
                table={tableA}
                onTable={setTableA}
                applyPreset={presetA}
                onFields={(f) => (fieldsRef.current.a = f)}
              />
              <ConnectForm
                side="b"
                datasources={meta.datasources}
                sessionId={sessionId}
                table={tableB}
                onTable={setTableB}
                applyPreset={presetB}
                onFields={(f) => (fieldsRef.current.b = f)}
              />
              <PresetsCard getFields={presetFields} onApply={applyPreset} resetSeq={resetSeq} />
              <OptionsCard
                strategies={meta.sample_strategies}
                options={options}
                onChange={setOptions}
                onReset={resetOptions}
              />
              <ActionRow
                sessionId={sessionId}
                tableA={tableA}
                tableB={tableB}
                options={options}
                onResult={setResultHtml}
              />
              <GenerationCard
                sessionId={sessionId}
                tableA={tableA}
                tableB={tableB}
                options={options}
                onResult={setResultHtml}
              />
              <TemplatesCard
                sessionId={sessionId}
                getTemplate={getTemplate}
                onApply={applyTemplate}
                onResult={setResultHtml}
              />
            </>
          )}
        </aside>

        {/* Results panel (actions land here from ticket 03 on) */}
        <main className="min-w-0 flex-1">
          <h2 className="mb-2 font-display text-xl font-bold text-ink">{t('results')}</h2>
          {resultHtml ? (
            <Card className="min-h-[420px]">
              {/* Server-rendered comparison cards (inline-styled, 1:1 legacy) */}
              <div
                data-testid="result-cards"
                className="overflow-x-auto"
                dangerouslySetInnerHTML={{ __html: resultHtml }}
              />
            </Card>
          ) : (
            <Card className="flex min-h-[420px] items-center justify-center">
              <div className="text-center">
                <div aria-hidden className="font-mono text-3xl text-ink-soft">
                  A ⇄ B
                </div>
                <p className="mt-3 max-w-[360px] font-mono text-[13px] text-muted">
                  {t('resultsEmpty')}
                </p>
              </div>
            </Card>
          )}
        </main>
      </div>
    </div>
  )
}
