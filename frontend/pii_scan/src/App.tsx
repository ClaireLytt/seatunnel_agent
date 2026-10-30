import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ApiError, mask, scan } from '@/api'
import { ReportView } from '@shared/components/ReportView'
import { fieldCls, labelCls, DIALECTS } from '@shared/constants'

export default function App() {
  const { t, i18n } = useTranslation()
  const [dir, setDir] = useState('examples/pii_demo')
  const [sql, setSql] = useState('')
  const [dialect, setDialect] = useState('hive')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')
  const [maskSql, setMaskSql] = useState('')
  const [maskWeak, setMaskWeak] = useState(true)
  const [copied, setCopied] = useState(false)

  const call = async (body: Parameters<typeof scan>[0]) => {
    setBusy(true)
    setError('')
    try {
      const res = await scan(body)
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
      if (e instanceof ApiError && e.code === 'bad_dir') {
        setError(t('bad_dir') + e.path)
      } else if (e instanceof ApiError && e.code === 'scan_failed') {
        setError(`${e.error}`) // legacy "Type: msg" parity
      } else {
        setError(String(e instanceof Error ? e.message : e))
      }
    } finally {
      setBusy(false)
    }
  }

  const runDir = () => {
    if (!dir.trim()) {
      setReport('')
      setError(t('empty_dir'))
      return
    }
    void call({ dir: dir.trim(), dialect, lang: i18n.language })
  }

  const runSql = () => {
    if (!sql.trim()) {
      setReport('')
      setError(t('empty_sql'))
      return
    }
    void call({ sql, dialect, lang: i18n.language })
  }

  const runMask = async () => {
    const body = sql.trim()
      ? { sql, dialect, min_confidence: maskWeak ? 'low' : 'high' }
      : { dir: dir.trim(), dialect, min_confidence: maskWeak ? 'low' : 'high' }
    if (!body.sql && !body.dir) {
      setError(t('empty_dir'))
      return
    }
    setBusy(true)
    setError('')
    setCopied(false)
    try {
      const res = await mask(body)
      setMaskSql(res.sql)
    } catch (e) {
      setMaskSql('')
      if (e instanceof ApiError && e.code === 'bad_dir') {
        setError(t('bad_dir') + e.path)
      } else {
        setError(String(e instanceof Error ? e.message : e))
      }
    } finally {
      setBusy(false)
    }
  }

  const copyMask = async () => {
    try {
      await navigator.clipboard.writeText(maskSql)
      setCopied(true)
    } catch {
      /* clipboard unavailable (http) — selection fallback not worth it */
    }
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / pii" titlePrefix="🔒" maxW="max-w-[660px]" />

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
            <label className={`${labelCls} mt-3`}>{t('dialect_label')}</label>
            <select
              value={dialect}
              onChange={(e) => setDialect(e.target.value)}
              className={fieldCls}
            >
              {DIALECTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <button
              onClick={runDir}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('scan_btn')}
            </button>
          </Card>

          <Card>
            <details>
              <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                {t('inline_acc')}
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                <div>
                  <label className={labelCls}>{t('sql_label')}</label>
                  <textarea
                    value={sql}
                    onChange={(e) => setSql(e.target.value)}
                    placeholder={t('sql_ph')}
                    rows={8}
                    spellCheck={false}
                    className={`${fieldCls} resize-y`}
                  />
                </div>
                <button
                  onClick={runSql}
                  disabled={busy}
                  className="w-full rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
                >
                  {busy ? t('running') : t('scan_sql_btn')}
                </button>
              </div>
            </details>
          </Card>

          <Card>
            <label className="flex cursor-pointer items-center gap-2 font-mono text-xs text-ink-soft">
              <input
                type="checkbox"
                checked={maskWeak}
                onChange={(e) => setMaskWeak(e.target.checked)}
              />
              {t('mask_conf_label')}
            </label>
            <button
              onClick={() => void runMask()}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('mask_btn')}
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
            {report && <ReportView className="pii-report" markdown={report} />}
            {!report && !error && !maskSql && <p className="text-sm text-muted">{t('dir_ph')}</p>}
          </Card>
          {maskSql && (
            <Card className="mt-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                  {t('mask_result_label')}
                </span>
                <button
                  onClick={() => void copyMask()}
                  className="rounded border-[1.5px] border-ink px-3 py-1 font-mono text-xs font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
                >
                  {copied ? t('mask_copied') : t('mask_copy')}
                </button>
              </div>
              <pre className="max-h-[480px] overflow-auto whitespace-pre font-mono text-xs leading-relaxed">
                {maskSql}
              </pre>
            </Card>
          )}
        </main>
      </div>
    </div>
  )
}
