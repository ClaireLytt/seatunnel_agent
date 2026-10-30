import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ApiError, migrateBatch, migrateText, type MigrateResponse } from '@/api'
import { ConfView } from '@/components/ConfView'
import { ReportView } from '@shared/components/ReportView'

export default function App() {
  const { t, i18n } = useTranslation()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<MigrateResponse | null>(null)
  const [jobsDir, setJobsDir] = useState('')
  const [outDir, setOutDir] = useState('')

  const run = async () => {
    if (!text.trim()) {
      setError(t('empty'))
      return
    }
    setBusy(true)
    setError('')
    try {
      setResult(await migrateText(text, i18n.language))
    } catch (e) {
      setResult(null)
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const runBatch = async () => {
    if (!jobsDir.trim()) {
      setError(t('empty'))
      return
    }
    setBusy(true)
    setError('')
    try {
      const res = await migrateBatch(jobsDir.trim(), outDir.trim(), i18n.language)
      setResult({ ok: true, source_kind: 'batch', conf: '', report: res.report })
    } catch (e) {
      setResult(null)
      if (e instanceof ApiError && e.code === 'bad_dir') {
        setError(t('bad_dir') + e.path)
      } else {
        setError(String(e))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / migrate" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('job_label')}
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={t('job_ph')}
              rows={14}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <button
              onClick={run}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('migrate_btn')}
            </button>
          </Card>

          <Card>
            <details>
              <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                {t('batch_acc')}
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                <div>
                  <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                    {t('dir_label')}
                  </label>
                  <input
                    value={jobsDir}
                    onChange={(e) => setJobsDir(e.target.value)}
                    placeholder={t('dir_ph')}
                    spellCheck={false}
                    className="w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink"
                  />
                </div>
                <div>
                  <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                    {t('out_label')}
                  </label>
                  <input
                    value={outDir}
                    onChange={(e) => setOutDir(e.target.value)}
                    placeholder={t('out_ph')}
                    spellCheck={false}
                    className="w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink"
                  />
                </div>
                <button
                  onClick={runBatch}
                  disabled={busy}
                  className="w-full rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
                >
                  {busy ? t('running') : t('batch_btn')}
                </button>
              </div>
            </details>
          </Card>
        </aside>

        <main className="min-w-0 flex-1">
          <Card>
            {error && (
              <div className="mb-3 font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {error}
              </div>
            )}
            {result && result.conf && <ConfView conf={result.conf} />}
            {result && (
              <div className="mt-4">
                <ReportView className="cm-report" markdown={result.report} />
              </div>
            )}
            {!result && !error && <p className="text-sm text-muted">{t('job_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
