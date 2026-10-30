import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { ApiError, runAssess } from '@/api'

export default function App() {
  const { t, i18n } = useTranslation()
  const [dir, setDir] = useState('examples/pipemigrate_demo')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')
  const [dagJson, setDagJson] = useState('')

  const toDagopt = () => {
    sessionStorage.setItem('seatunnel.handoff.dagopt', dagJson)
    window.location.href = '/dagopt/'
  }

  const run = async (useText: boolean) => {
    const src = useText ? text : dir
    if (!src.trim()) {
      setError(t('empty_input'))
      setReport('')
      return
    }
    setBusy(true)
    setError('')
    try {
      const res = await runAssess(useText ? null : dir.trim(), useText ? text : null, i18n.language)
      setReport(res.report ?? '')
      const dag = res.result['migration_dag'] as Record<string, unknown> | undefined
      setDagJson(dag && Object.keys(dag).length ? JSON.stringify(dag) : '')
    } catch (e) {
      setReport('')
      setDagJson('')
      if (e instanceof ApiError && e.code === 'bad_dir') {
        setError(t('bad_dir') + e.path)
      } else {
        setError(String(e))
      }
    } finally {
      setBusy(false)
    }
  }

  const clear = () => {
    setDir('examples/pipemigrate_demo')
    setText('')
    setError('')
    setReport('')
    setDagJson('')
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / pipemigrate" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('dir_label')}
            </label>
            <input
              value={dir}
              onChange={(e) => setDir(e.target.value)}
              placeholder={t('dir_ph')}
              spellCheck={false}
              className="w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <button
              onClick={() => run(false)}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('run_btn')}
            </button>
            <button
              onClick={clear}
              disabled={busy}
              className="mt-2 w-full rounded border-[1.5px] border-transparent px-4 py-2 font-mono text-sm text-ink-soft transition hover:border-line disabled:opacity-50"
            >
              {t('clear_btn')}
            </button>
          </Card>

          <Card>
            <details>
              <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                {t('text_acc')}
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                <label className="block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                  {t('text_label')}
                </label>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={t('text_ph')}
                  rows={10}
                  spellCheck={false}
                  className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
                />
                <button
                  onClick={() => run(true)}
                  disabled={busy}
                  className="w-full rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
                >
                  {t('run_text_btn')}
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
            {report && dagJson && (
              <button
                onClick={toDagopt}
                className="mb-4 w-full rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
              >
                {t('to_dagopt')}
              </button>
            )}
            {report && <ReportView markdown={report} />}
            {!report && !error && <p className="text-sm text-muted">{t('report_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
