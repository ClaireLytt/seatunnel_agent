import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { ApiError, diff } from '@/api'
import { ReportView } from '@shared/components/ReportView'
import { fieldCls, labelCls, textareaCls, DIALECTS } from '@shared/constants'


export default function App() {
  const { t, i18n } = useTranslation()
  const [dialect, setDialect] = useState('hive')
  const [oldSql, setOldSql] = useState('')
  const [newSql, setNewSql] = useState('')
  const [oldDir, setOldDir] = useState('examples/schema_drift_demo/old')
  const [newDir, setNewDir] = useState('examples/schema_drift_demo/new')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')

  const call = async (body: Parameters<typeof diff>[0]) => {
    setBusy(true)
    setError('')
    try {
      const res = await diff(body)
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
      if (e instanceof ApiError && e.code === 'bad_path') {
        setError(t('bad_path') + e.path)
      } else if (e instanceof ApiError && e.code === 'diff_failed') {
        setError(`⚠️ ${e.error}`)  // legacy "⚠️ Type: msg" parity
      } else {
        setError(String(e instanceof Error ? e.message : e))
      }
    } finally {
      setBusy(false)
    }
  }

  const runSql = () => {
    if (!oldSql.trim() || !newSql.trim()) {
      setReport('')
      setError(t('empty_sql'))
      return
    }
    void call({ old_sql: oldSql, new_sql: newSql, dialect, lang: i18n.language })
  }

  const runDirs = () => {
    if (!oldDir.trim() || !newDir.trim()) {
      setReport('')
      setError(t('empty_dirs'))
      return
    }
    void call({
      old_path: oldDir.trim(),
      new_path: newDir.trim(),
      dialect,
      lang: i18n.language,
    })
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <span className="mb-3 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            data / schemadrift
          </span>
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink">🧬 {t('title')}</h1>
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
            <label className={labelCls}>{t('dialect_label')}</label>
            <select value={dialect} onChange={(e) => setDialect(e.target.value)} className={fieldCls}>
              {DIALECTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <label className={`${labelCls} mt-3`}>{t('old_label')}</label>
            <textarea
              value={oldSql}
              onChange={(e) => setOldSql(e.target.value)}
              placeholder={t('old_ph')}
              rows={8}
              spellCheck={false}
              className={textareaCls}
            />
            <label className={`${labelCls} mt-3`}>{t('new_label')}</label>
            <textarea
              value={newSql}
              onChange={(e) => setNewSql(e.target.value)}
              placeholder={t('new_ph')}
              rows={8}
              spellCheck={false}
              className={textareaCls}
            />
            <button
              onClick={runSql}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('diff_btn')}
            </button>
          </Card>

          <Card>
            <details>
              <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                {t('dirs_acc')}
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                <div>
                  <label className={labelCls}>{t('old_dir_label')}</label>
                  <input
                    value={oldDir}
                    onChange={(e) => setOldDir(e.target.value)}
                    spellCheck={false}
                    className={fieldCls}
                  />
                </div>
                <div>
                  <label className={labelCls}>{t('new_dir_label')}</label>
                  <input
                    value={newDir}
                    onChange={(e) => setNewDir(e.target.value)}
                    spellCheck={false}
                    className={fieldCls}
                  />
                </div>
                <button
                  onClick={runDirs}
                  disabled={busy}
                  className="w-full rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
                >
                  {busy ? t('running') : t('dirs_btn')}
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
            {report && <ReportView className="sd-report" markdown={report} />}
            {!report && !error && <p className="text-sm text-muted">{t('old_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
