import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { DATASKEW_SQL_KEY } from '@shared/bridge'
import { analyze, getSessionId } from '@/api'
import { HistoryPanel } from '@/components/HistoryPanel'
import { downloadText, fieldCls, labelCls, smallBtnCls } from '@/ui'
import { ReportView } from '@/components/ReportView'
import { SqlView } from '@/components/SqlView'

const DIALECTS: [string, string][] = [
  ['Spark SQL (Spark 3)', 'spark'],
  ['MaxCompute SQL', 'maxcompute'],
  ['Hive SQL', 'hive'],
]


export default function App() {
  const { t, i18n } = useTranslation()
  const [sessionId, setSessionId] = useState('')
  const [sql, setSql] = useState('')
  const [dialect, setDialect] = useState('spark')
  const [mode, setMode] = useState<'static' | 'llm'>('static')
  const [busy, setBusy] = useState(false)
  const [runningNote, setRunningNote] = useState('')
  const [error, setError] = useState('')
  const [report, setReport] = useState('')
  const [optimized, setOptimized] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getSessionId().then(setSessionId).catch(() => {})
    // SQL handed over from sql_review / data comparison (localStorage bridge)
    try {
      const handed = localStorage.getItem(DATASKEW_SQL_KEY)
      if (handed) {
        setSql(handed)
        localStorage.removeItem(DATASKEW_SQL_KEY)
      }
    } catch {
      /* storage unavailable — nothing to pick up */
    }
  }, [])

  const run = async () => {
    if (!sql.trim()) return
    setBusy(true)
    setError('')
    setOptimized('')
    setRunningNote(t(mode === 'llm' ? 'running_llm' : 'running_static'))
    try {
      const res = await analyze({
        sql,
        dialect,
        mode,
        sample: 10,
        lang: i18n.language,
        session_id: sessionId,
      })
      setReport(res.report)
      setOptimized(res.optimized_sql)
    } catch (e) {
      setReport('')
      setError(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy(false)
      setRunningNote('')
    }
  }

  const clear = () => {
    setSql('')
    setReport('')
    setOptimized('')
    setError('')
  }

  const onUpload = (f: File | undefined) => {
    if (!f) return
    f.text().then((text) => setSql(text.slice(0, 200_000)))
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <span className="mb-3 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            data / dataskew
          </span>
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink">⚖️ {t('title')}</h1>
          <p className="mt-2 max-w-[680px] text-sm text-muted">{t('subtitle')}</p>
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
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[460px]">
          <Card>
            <label className={labelCls}>{t('sql_label')}</label>
            <textarea
              id="dsk-sql-box"
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              placeholder={t('sql_ph')}
              rows={14}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <div className="mt-3 flex gap-3">
              <div className="flex-1">
                <label className={labelCls}>{t('dialect')}</label>
                <select
                  value={dialect}
                  onChange={(e) => setDialect(e.target.value)}
                  className={fieldCls}
                >
                  {DIALECTS.map(([label, v]) => (
                    <option key={v} value={v}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className={labelCls}>{t('mode')}</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as 'static' | 'llm')}
                  className={fieldCls}
                >
                  <option value="static">{t('mode_static')}</option>
                  <option value="llm">{t('mode_llm')}</option>
                </select>
              </div>
            </div>
            <button
              onClick={run}
              disabled={busy || !sql.trim()}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {t('analyze_btn')}
            </button>
            <div className="mt-2 flex gap-2">
              <button onClick={() => fileRef.current?.click()} className={smallBtnCls}>
                {t('upload_btn')}
              </button>
              <input
                ref={fileRef}
                type="file"
                accept=".sql,.txt,.hql"
                className="hidden"
                onChange={(e) => {
                  onUpload(e.target.files?.[0])
                  e.target.value = ''
                }}
              />
              <button onClick={clear} className={smallBtnCls}>
                {t('clear_btn')}
              </button>
            </div>
          </Card>

          <HistoryPanel
            onLoad={(s, d) => {
              setSql(s)
              setDialect(d)
            }}
          />
        </aside>

        <main className="flex min-w-0 flex-1 flex-col gap-4">
          <Card>
            {error && (
              <div className="mb-3 font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {error}
              </div>
            )}
            {busy && runningNote && <p className="text-sm text-muted">⏳ {runningNote}</p>}
            {!busy && report && (
              <div className="dsk-report-card">
                <div className="mb-3 flex gap-2">
                  <button
                    onClick={() => downloadText('data_skew_report.md', report)}
                    className={smallBtnCls}
                  >
                    {t('download_report')}
                  </button>
                  {optimized && (
                    <button
                      onClick={() => downloadText('my_task_optimized.sql', optimized)}
                      className={smallBtnCls}
                    >
                      {t('download_sql')}
                    </button>
                  )}
                </div>
                <ReportView markdown={report} />
              </div>
            )}
            {!busy && !report && !error && (
              <p className="text-sm italic text-muted">{t('report_placeholder')}</p>
            )}
          </Card>
          {!busy && optimized && (
            <Card>
              <SqlView sql={optimized} />
            </Card>
          )}
        </main>
      </div>
    </div>
  )
}
