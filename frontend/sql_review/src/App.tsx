import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { load as parseYaml } from 'js-yaml'
import { DIALECT_NAMES, DIALECTS, fix, review } from '@/api'
import { Collapsible } from '@/components/Collapsible'
import { ReportView } from '@/components/ReportView'
import { Card } from '@shared/components/card'

const inputCls =
  'w-full rounded border border-line bg-card px-3 py-2 font-mono text-sm text-fg ' +
  'outline-none focus:border-ink'

const labelCls = 'mb-1 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

export default function App() {
  const { t, i18n } = useTranslation()
  const lang: 'zh' | 'en' = i18n.language.startsWith('zh') ? 'zh' : 'en'

  const [sql, setSql] = useState('')
  const [dialect, setDialect] = useState('hive')
  const [mode, setMode] = useState<'static' | 'agent'>('static')
  const [ddl, setDdl] = useState('')
  const [rulesText, setRulesText] = useState('')

  const [reviewing, setReviewing] = useState(false)
  const [fixing, setFixing] = useState(false)
  const [report, setReport] = useState('')
  const [fixedSql, setFixedSql] = useState('')
  const [error, setError] = useState('')

  // YAML rules → inline dict for the API (the legacy page parsed server-side)
  const parseRules = (): Record<string, unknown> | undefined => {
    const text = rulesText.trim()
    if (!text) return undefined
    const parsed = parseYaml(text)
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error(text.slice(0, 80))
    }
    return parsed as Record<string, unknown>
  }

  const onReview = async () => {
    if (!sql.trim()) {
      setError(t('inputSqlFirst'))
      return
    }
    setReviewing(true)
    setError('')
    setFixedSql('')
    let rules: Record<string, unknown> | undefined
    try {
      rules = parseRules()
    } catch (e) {
      setError(`${t('rulesInvalid')}: ${e instanceof Error ? e.message : e}`)
      setReviewing(false)
      return
    }
    try {
      const r = await review({
        sql,
        dialect,
        mode,
        lang,
        rules,
        schema_ddl: ddl.trim() || undefined,
      })
      setReport(r.report)
    } catch (e) {
      setError(`${t('reviewFailed')}: ${e instanceof Error ? e.message : e}`)
    } finally {
      setReviewing(false)
    }
  }

  const onFix = async () => {
    if (!sql.trim() || !report) {
      setFixedSql(t('fixNeedReview'))
      return
    }
    setFixing(true)
    if (mode === 'agent') setFixedSql(t('fixGenerating'))
    let rules: Record<string, unknown> | undefined
    try {
      rules = parseRules()
    } catch {
      rules = undefined // review already surfaced the parse error
    }
    try {
      const r = await fix({ sql, dialect, mode, report, rules, lang })
      setFixedSql(r.fixed_sql)
    } catch (e) {
      const msg = e instanceof Error ? e.message : `${e}`
      setFixedSql(
        msg.includes('no mechanically fixable')
          ? t('fixNoneStatic')
          : `${t('fixFailed')}: ${msg}`,
      )
    } finally {
      setFixing(false)
    }
  }

  const onClear = () => {
    setSql('')
    setDdl('')
    setRulesText('')
    setReport('')
    setFixedSql('')
    setError('')
  }

  const onDownload = () => {
    const blob = new Blob([report], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'sql_review_report.md'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="mx-auto max-w-[1020px] px-4 py-10">
      <motion.header
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex items-start justify-between gap-4"
      >
        <div>
          <span className="mb-4 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            data / sqlreview
          </span>
          <h1 className="font-display text-4xl font-bold tracking-tight text-ink">{t('title')}</h1>
          <p className="mt-3 max-w-[620px] text-muted">{t('subtitle')}</p>
        </div>
        <a
          href="/"
          title={t('home')}
          className="shrink-0 rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
        >
          {t('home')}
        </a>
      </motion.header>

      <Card className="mt-8">
        <label className={labelCls} htmlFor="sql">
          SQL
        </label>
        <textarea
          id="sql"
          className={`${inputCls} min-h-[260px]`}
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          placeholder={t('sqlPlaceholder')}
          spellCheck={false}
        />
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-[1fr_1.6fr_auto]">
          <div>
            <label className={labelCls} htmlFor="dialect">
              {t('dialect')}
            </label>
            <select
              id="dialect"
              className={inputCls}
              value={dialect}
              onChange={(e) => setDialect(e.target.value)}
            >
              {DIALECTS.map((d) => (
                <option key={d} value={d}>
                  {DIALECT_NAMES[d]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <span className={labelCls}>{t('mode')}</span>
            <div className="flex gap-5 pt-2 font-mono text-sm text-fg">
              {(['static', 'agent'] as const).map((m) => (
                <label key={m} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="mode"
                    checked={mode === m}
                    onChange={() => setMode(m)}
                    className="h-4 w-4 accent-[var(--ink)]"
                  />
                  {m === 'static' ? t('modeStatic') : t('modeLlm')}
                </label>
              ))}
            </div>
          </div>
          <div className="flex items-end gap-3">
            <button
              onClick={onReview}
              disabled={reviewing || fixing}
              className="rounded border-[1.5px] border-ink bg-ink px-6 py-2 font-mono text-sm text-paper transition enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard disabled:opacity-50"
            >
              {reviewing ? t('reviewing') : t('reviewBtn')}
            </button>
            <button
              onClick={onFix}
              disabled={reviewing || fixing}
              className="rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm text-ink transition enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard disabled:opacity-50"
            >
              {t('fixBtn')}
            </button>
            <button
              onClick={onClear}
              disabled={reviewing || fixing}
              className="rounded border-[1.5px] border-line px-4 py-2 font-mono text-sm text-muted transition enabled:hover:border-ink enabled:hover:text-ink disabled:opacity-50"
            >
              {t('clearBtn')}
            </button>
          </div>
        </div>
        <Collapsible title={t('ddlAccordion')}>
          <label className={labelCls} htmlFor="ddl">
            {t('ddlLabel')}
          </label>
          <textarea
            id="ddl"
            className={`${inputCls} min-h-[140px]`}
            value={ddl}
            onChange={(e) => setDdl(e.target.value)}
            placeholder="CREATE TABLE ods.user_log (user_id BIGINT, dt STRING) ..."
            spellCheck={false}
          />
        </Collapsible>
        <Collapsible title={t('rulesAccordion')}>
          <label className={labelCls} htmlFor="rules">
            {t('rulesLabel')}
          </label>
          <textarea
            id="rules"
            className={`${inputCls} min-h-[140px]`}
            value={rulesText}
            onChange={(e) => setRulesText(e.target.value)}
            placeholder={t('rulesPlaceholder')}
            spellCheck={false}
          />
        </Collapsible>
      </Card>

      <AnimatePresence>
        {error && (
          <motion.p
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-4 font-mono text-sm text-[var(--accent)]"
          >
            {error}
          </motion.p>
        )}
      </AnimatePresence>

      <section className="mt-6">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-display text-xl font-bold text-ink">{t('report')}</h2>
          {report && (
            <button
              onClick={onDownload}
              className="rounded border-[1.5px] border-ink px-3 py-1.5 font-mono text-[13px] text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
            >
              {t('downloadReport')}
            </button>
          )}
        </div>
        <Card>
          {report ? (
            <ReportView markdown={report} />
          ) : (
            <p className="italic text-muted">{t('reportPlaceholder')}</p>
          )}
        </Card>
      </section>

      <AnimatePresence>
        {fixedSql && (
          <motion.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6"
          >
            <h2 className="mb-2 font-display text-xl font-bold text-ink">{t('fixedSql')}</h2>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded border border-line bg-card p-4 font-mono text-[13px] leading-6 text-fg">
              {fixedSql}
            </pre>
          </motion.section>
        )}
      </AnimatePresence>
    </div>
  )
}
