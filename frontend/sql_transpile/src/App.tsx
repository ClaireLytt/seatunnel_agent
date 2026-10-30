import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { TRANSPILE_SQL_KEY } from '@shared/bridge'
import { ApiError, fetchDialects, requestAdvice, translateBatch, translateSql } from '@/api'
import { ReportView } from '@shared/components/ReportView'
import { SqlView } from '@/components/SqlView'
import { fieldCls, labelCls } from '@shared/constants'

const FALLBACK_DIALECTS = ['hive', 'spark', 'doris', 'starrocks']

export default function App() {
  const { t, i18n } = useTranslation()
  const [dialects, setDialects] = useState<string[]>(FALLBACK_DIALECTS)
  const [src, setSrc] = useState('auto')
  const [dst, setDst] = useState('doris')
  const [text, setText] = useState('')
  const [dir, setDir] = useState('')
  const [outDir, setOutDir] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [outputSql, setOutputSql] = useState('')
  const [report, setReport] = useState('')
  // the inputs the last successful translate ran with — advice replays them
  const [advised, setAdvised] = useState<{ sql: string; to: string; from: string } | null>(null)
  const [advice, setAdvice] = useState('')
  const [advising, setAdvising] = useState(false)

  useEffect(() => {
    fetchDialects()
      .then(setDialects)
      .catch(() => {})
    // SQL handed over from the review page (localStorage bridge) — drain it
    try {
      const handed = localStorage.getItem(TRANSPILE_SQL_KEY)
      if (handed) {
        setText(handed)
        localStorage.removeItem(TRANSPILE_SQL_KEY)
      }
    } catch {
      /* storage unavailable — nothing to pick up */
    }
  }, [])

  const reset = () => {
    setError('')
    setOutputSql('')
    setReport('')
    setAdvised(null)
    setAdvice('')
  }

  const run = async () => {
    if (!text.trim()) {
      reset()
      setError(t('empty_sql'))
      return
    }
    setBusy(true)
    reset()
    try {
      const res = await translateSql(text, dst, src, i18n.language)
      // legacy parity: hide the code block when no statement translated OK
      const anyOk = res.statements?.some((s) => s.ok === true)
      setOutputSql(anyOk ? (res.output_sql ?? '') : '')
      setReport(res.report ?? '')
      setAdvised({ sql: text, to: dst, from: src })
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const runBatch = async () => {
    if (!dir.trim()) {
      reset()
      setError(t('empty_dir'))
      return
    }
    setBusy(true)
    reset()
    try {
      const res = await translateBatch(dir.trim(), outDir.trim(), dst, src, i18n.language)
      setReport((res.report as string) ?? '')
    } catch (e) {
      if (e instanceof ApiError && e.code === 'bad_dir') {
        setError(t('bad_dir') + e.path)
      } else {
        setError(String(e))
      }
    } finally {
      setBusy(false)
    }
  }

  const runAdvice = async () => {
    if (!advised) {
      setAdvice(t('advice_none'))
      return
    }
    setAdvising(true)
    try {
      const res = await requestAdvice(advised.sql, advised.to, advised.from, i18n.language)
      if (res.status === 'ok' && res.advice) setAdvice(res.advice)
      else if (res.status === 'no_key') setAdvice(t('advice_no_key'))
      else if (res.status === 'error') setAdvice(`${res.detail ?? 'LLM error'}`)
      else setAdvice(t('advice_none'))
    } catch (e) {
      setAdvice(String(e))
    } finally {
      setAdvising(false)
    }
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / transpile" titlePrefix="🔁" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className={labelCls}>{t('src_label')}</label>
                <select value={src} onChange={(e) => setSrc(e.target.value)} className={fieldCls}>
                  <option value="auto">{t('src_auto')}</option>
                  {dialects.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className={labelCls}>{t('dst_label')}</label>
                <select value={dst} onChange={(e) => setDst(e.target.value)} className={fieldCls}>
                  {dialects.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <label className={`${labelCls} mt-3`}>{t('sql_label')}</label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={t('sql_ph')}
              rows={10}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <button
              onClick={run}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('translate_btn')}
            </button>
          </Card>

          <Card>
            <details>
              <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                {t('batch_acc')}
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                <div>
                  <label className={labelCls}>{t('dir_label')}</label>
                  <input
                    value={dir}
                    onChange={(e) => setDir(e.target.value)}
                    placeholder={t('dir_ph')}
                    spellCheck={false}
                    className={fieldCls}
                  />
                </div>
                <div>
                  <label className={labelCls}>{t('out_label')}</label>
                  <input
                    value={outDir}
                    onChange={(e) => setOutDir(e.target.value)}
                    placeholder={t('out_ph')}
                    spellCheck={false}
                    className={fieldCls}
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
            {outputSql && (
              <div className="mb-4">
                <SqlView sql={outputSql} />
              </div>
            )}
            {report && <ReportView className="tr-report" markdown={report} />}
            {!report && !error && <p className="text-sm text-muted">{t('sql_ph')}</p>}
          </Card>

          <div className="mt-4">
            <Card>
              <details>
                <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                  {t('advice_acc')}
                </summary>
                <div className="mt-3">
                  <button
                    onClick={runAdvice}
                    disabled={advising}
                    className="rounded border-[1.5px] border-ink px-3 py-1.5 font-mono text-xs font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
                  >
                    {advising ? t('advising') : t('advice_btn')}
                  </button>
                  {advice && (
                    <div className="mt-3">
                      <ReportView className="tr-report" markdown={advice} />
                    </div>
                  )}
                </div>
              </details>
            </Card>
          </div>
        </main>
      </div>
    </div>
  )
}
