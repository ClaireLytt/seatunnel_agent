import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { ApiError, checkDir, formatSql } from '@/api'
import { ReportView } from '@/components/ReportView'

const DIALECTS = [
  'hive',
  'spark',
  'mysql',
  'postgresql',
  'clickhouse',
  'doris',
  'starrocks',
]

export default function App() {
  const { t, i18n } = useTranslation()
  const [text, setText] = useState('')
  const [dialect, setDialect] = useState('hive')
  const [dir, setDir] = useState('examples/sqlfmt_demo')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')

  const run = async () => {
    if (!text.trim()) {
      setError(t('empty_sql'))
      setReport('')
      return
    }
    setBusy(true)
    setError('')
    try {
      const res = await formatSql(text, dialect, i18n.language)
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const runDir = async () => {
    if (!dir.trim()) {
      setError(t('empty_dir'))
      setReport('')
      return
    }
    setBusy(true)
    setError('')
    try {
      const res = await checkDir(dir.trim(), dialect, i18n.language)
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
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
      <header className="flex items-start justify-between gap-4">
        <div>
          <span className="mb-3 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            data / sqlfmt
          </span>
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink">🪄 {t('title')}</h1>
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

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('sql_label')}
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={t('sql_ph')}
              rows={12}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className="mb-2 mt-3 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('dialect_label')}
            </label>
            <select
              value={dialect}
              onChange={(e) => setDialect(e.target.value)}
              className="w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink"
            >
              {DIALECTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <button
              onClick={run}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('fmt_btn')}
            </button>
          </Card>

          <Card>
            <details>
              <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                {t('dir_acc')}
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                <div>
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
                </div>
                <button
                  onClick={runDir}
                  disabled={busy}
                  className="w-full rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
                >
                  {busy ? t('running') : t('dir_btn')}
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
            {report && <ReportView markdown={report} />}
            {!report && !error && <p className="text-sm text-muted">{t('sql_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
