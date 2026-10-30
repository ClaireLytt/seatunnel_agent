import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from './card'
import { PageHeader } from './PageHeader'
import { ReportView } from './ReportView'
import { ApiError } from '../api'
import { fieldCls, labelCls, DIALECTS } from '../constants'

/**
 * The standard scan-agent page: optional extra textarea (a contract, an
 * exemption list), directory input + dialect + primary button, a details
 * section with a pasted-SQL textarea, and the report pane. Four
 * governance pages shared this exact shape as copies; the page is now a
 * config, the i18n keys stay per-app (dir_label, dir_ph, dialect_label,
 * scan_btn, inline_acc, sql_label, sql_ph, scan_sql_btn, empty_dir,
 * empty_sql, bad_dir, running — plus extra_label/extra_ph/empty_extra
 * when `extra` is set).
 */
export type ScanBody = {
  sql?: string
  dir?: string
  dialect: string
  lang: string
} & Record<string, unknown>

export interface ScanPageConfig {
  badge: string // e.g. "data / metaquality"
  titlePrefix: string // header glyph
  errorCode: string // structured failure code, e.g. "metaquality_failed"
  reportClass: string // report wrapper class, e.g. "metaquality-report"
  scan: (body: ScanBody) => Promise<{ report: string | null }>
  extra?: {
    bodyKey: string // request field name, e.g. "contract"
    required: boolean
    rows?: number
    mono?: boolean
  }
  detailsOpen?: boolean // open the pasted-SQL section by default
  sqlRows?: number
  defaultDir?: string
}

export function ScanPage({ cfg }: { cfg: ScanPageConfig }) {
  const { t, i18n } = useTranslation()
  const [extra, setExtra] = useState('')
  const [dir, setDir] = useState(cfg.defaultDir ?? 'examples/pii_demo')
  const [sql, setSql] = useState('')
  const [dialect, setDialect] = useState('hive')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')

  const call = async (body: ScanBody) => {
    setBusy(true)
    setError('')
    try {
      const res = await cfg.scan(body)
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
      if (e instanceof ApiError && e.code === 'bad_dir') {
        setError(t('bad_dir') + e.path)
      } else if (e instanceof ApiError && e.code === cfg.errorCode) {
        setError(`⚠️ ${e.error}`)
      } else {
        setError(String(e instanceof Error ? e.message : e))
      }
    } finally {
      setBusy(false)
    }
  }

  const extraBody = (): Record<string, unknown> | null => {
    if (!cfg.extra) return {}
    if (cfg.extra.required && !extra.trim()) {
      setReport('')
      setError(t('empty_extra'))
      return null
    }
    return { [cfg.extra.bodyKey]: extra }
  }

  const runDir = () => {
    const eb = extraBody()
    if (eb === null) return
    if (!dir.trim()) {
      setReport('')
      setError(t('empty_dir'))
      return
    }
    void call({ dir: dir.trim(), dialect, lang: i18n.language, ...eb })
  }

  const runSql = () => {
    const eb = extraBody()
    if (eb === null) return
    if (!sql.trim()) {
      setReport('')
      setError(t('empty_sql'))
      return
    }
    void call({ sql, dialect, lang: i18n.language, ...eb })
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge={cfg.badge} titlePrefix={cfg.titlePrefix} maxW="max-w-[660px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            {cfg.extra && (
              <>
                <label className={labelCls}>{t('extra_label')}</label>
                <textarea
                  value={extra}
                  onChange={(e) => setExtra(e.target.value)}
                  placeholder={t('extra_ph')}
                  rows={cfg.extra.rows ?? 10}
                  spellCheck={false}
                  className={`${fieldCls} resize-y${cfg.extra.mono ? ' font-mono' : ''}`}
                />
              </>
            )}
            <label className={`${labelCls}${cfg.extra ? ' mt-3' : ''}`}>{t('dir_label')}</label>
            <input
              value={dir}
              onChange={(e) => setDir(e.target.value)}
              placeholder={t('dir_ph')}
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
              onClick={runDir}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('scan_btn')}
            </button>
          </Card>

          <Card>
            <details open={cfg.detailsOpen}>
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
                    rows={cfg.sqlRows ?? 8}
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
        </aside>

        <main className="min-w-0 flex-1">
          <Card>
            {error && (
              <div className="mb-3 font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {error}
              </div>
            )}
            {report && <ReportView className={cfg.reportClass} markdown={report} />}
            {!report && !error && <p className="text-sm text-muted">{t(cfg.extra ? 'extra_ph' : 'sql_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
