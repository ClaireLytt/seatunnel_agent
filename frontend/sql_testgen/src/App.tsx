import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { DIALECTS } from '@shared/constants'
import { generateData } from '@/api'
import { ReportView } from '@/components/ReportView'

// Same demo prefill as the legacy page (_DEMO_SQL) — a 2-table JOIN with a
// partition filter and an IN list, so first-time users get a telling report.
const DEMO_SQL = `SELECT u.user_id, u.user_name, sum(o.amount) AS pay_amount
FROM dwd.user_info u
JOIN dwd.order_pay o ON u.user_id = o.user_id
WHERE o.dt = '2024-01-01' AND o.status IN ('PAID', 'DONE')
GROUP BY u.user_id, u.user_name`

const fieldCls =
  'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'
const textareaCls =
  'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'
const labelCls =
  'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

export default function App() {
  const { t, i18n } = useTranslation()
  const [sql, setSql] = useState(DEMO_SQL)
  const [ddl, setDdl] = useState('')
  const [dialect, setDialect] = useState('hive')
  const [rows, setRows] = useState(5)
  const [validate, setValidate] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')

  const run = async () => {
    if (!sql.trim()) {
      setError(t('empty_sql'))
      setReport('')
      return
    }
    setBusy(true)
    setError('')
    try {
      const res = await generateData({
        sql,
        ddl,
        rows,
        dialect,
        validate_sqlite: validate,
        lang: i18n.language,
      })
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <span className="mb-3 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            data / testgen
          </span>
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink">🧪 {t('title')}</h1>
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
            <label className={labelCls}>{t('sql_label')}</label>
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              placeholder={t('sql_ph')}
              rows={8}
              spellCheck={false}
              className={textareaCls}
            />
            <label className={`${labelCls} mt-3`}>{t('ddl_label')}</label>
            <textarea
              value={ddl}
              onChange={(e) => setDdl(e.target.value)}
              placeholder={t('ddl_ph')}
              rows={5}
              spellCheck={false}
              className={textareaCls}
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
            <label className={`${labelCls} mt-3`}>
              {t('rows_label')}: <span className="normal-case">{rows}</span>
            </label>
            <input
              type="range"
              min={1}
              max={50}
              step={1}
              value={rows}
              onChange={(e) => setRows(Number(e.target.value))}
              className="w-full accent-[var(--ink)]"
            />
            <label className="mt-3 flex cursor-pointer items-center gap-2 font-mono text-[13px] text-ink">
              <input
                type="checkbox"
                checked={validate}
                onChange={(e) => setValidate(e.target.checked)}
                className="accent-[var(--ink)]"
              />
              {t('validate_label')}
            </label>
            <button
              onClick={run}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('gen_btn')}
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
            {!report && !error && <p className="text-sm text-muted">{t('sql_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
