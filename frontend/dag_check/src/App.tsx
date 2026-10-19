import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { ApiError, checkDag } from '@/api'
import { ReportView } from '@/components/ReportView'

// Pinned to the legacy _DIALECTS tuple (agents/data/dag_check/ui.py).
const DIALECTS = [
  'hive',
  'spark',
  'mysql',
  'postgresql',
  'clickhouse',
  'doris',
  'starrocks',
]

const fieldCls =
  'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'
const labelCls =
  'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

export default function App() {
  const { t, i18n } = useTranslation()
  const [dir, setDir] = useState('examples/dagcheck_demo')
  const [stDir, setStDir] = useState('')
  const [dialect, setDialect] = useState('hive')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')

  const run = async () => {
    if (!dir.trim()) {
      setReport('')
      setError(t('empty_dir'))
      return
    }
    setBusy(true)
    setError('')
    try {
      const res = await checkDag({
        sql_dir: dir.trim(),
        seatunnel_dir: stDir.trim() || undefined,
        dialect,
        lang: i18n.language,
      })
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
      if (e instanceof ApiError && e.code === 'bad_dir') {
        setError(t('bad_dir') + e.path)
      } else if (e instanceof ApiError && e.code === 'check_failed') {
        setError(`⚠️ ${e.error}`) // legacy "⚠️ Type: msg" parity
      } else {
        setError(String(e instanceof Error ? e.message : e))
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
            data / dagcheck
          </span>
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink">🗓️ {t('title')}</h1>
          <p className="mt-2 max-w-[660px] text-sm text-muted">{t('subtitle')}</p>
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
            <label className={labelCls}>{t('dir_label')}</label>
            <input
              value={dir}
              onChange={(e) => setDir(e.target.value)}
              placeholder={t('dir_ph')}
              spellCheck={false}
              className={fieldCls}
            />
            <label className={`${labelCls} mt-3`}>{t('st_label')}</label>
            <input
              value={stDir}
              onChange={(e) => setStDir(e.target.value)}
              placeholder={t('st_ph')}
              spellCheck={false}
              className={fieldCls}
            />
            <label className={`${labelCls} mt-3`}>{t('dialect_label')}</label>
            <select value={dialect} onChange={(e) => setDialect(e.target.value)} className={fieldCls}>
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
              {busy ? t('running') : t('check_btn')}
            </button>
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
            {!report && !error && <p className="text-sm text-muted">{t('dir_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
