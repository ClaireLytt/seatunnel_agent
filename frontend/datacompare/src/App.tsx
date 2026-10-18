import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { createSession, defaultCompareOptions, fetchMeta, type Meta } from '@/api'
import { ActionRow } from '@/components/ActionRow'
import { ConnectForm } from '@/components/ConnectForm'
import { Card } from '@shared/components/card'

export default function App() {
  const { t } = useTranslation()

  const [meta, setMeta] = useState<Meta | null>(null)
  const [sessionId, setSessionId] = useState('')
  const [error, setError] = useState('')
  const [tableA, setTableA] = useState('')
  const [tableB, setTableB] = useState('')
  const [resultHtml, setResultHtml] = useState('')

  // Ticket 05 (options block) replaces this constant with live form state.
  const options = defaultCompareOptions

  useEffect(() => {
    fetchMeta()
      .then(setMeta)
      .catch((e) => setError(String(e)))
    createSession()
      .then(setSessionId)
      .catch((e) => setError(String(e)))
  }, [])

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
              />
              <ConnectForm
                side="b"
                datasources={meta.datasources}
                sessionId={sessionId}
                table={tableB}
                onTable={setTableB}
              />
              <ActionRow
                sessionId={sessionId}
                tableA={tableA}
                tableB={tableB}
                options={options}
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
