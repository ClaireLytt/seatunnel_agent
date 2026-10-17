import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { load as parseYaml } from 'js-yaml'
import {
  ApiError,
  DIALECT_ALIASES,
  DIALECT_NAMES,
  DIALECTS,
  fetchStats,
  fix,
  review,
  type StatsResponse,
  type TopCategory,
} from '@/api'
import { CHECK_CATALOG_EN } from '@/i18n'
import { Collapsible } from '@/components/Collapsible'
import { ReportView } from '@/components/ReportView'
import { TrendChart } from '@/components/TrendChart'
import { Card } from '@shared/components/card'

const inputCls =
  'w-full rounded border border-line bg-card px-3 py-2 font-mono text-sm text-fg ' +
  'outline-none focus:border-ink'

const labelCls = 'mb-1 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

// top_categories labels come back Chinese (report.CHECK_CATALOG); map the
// category key to English when the page language is en
const categoryLabel = (c: TopCategory, lang: 'zh' | 'en') =>
  lang === 'en' && c.category ? (CHECK_CATALOG_EN[c.category] ?? c.category) : c.label

export default function App() {
  const { t, i18n } = useTranslation()
  const lang: 'zh' | 'en' = i18n.language.startsWith('zh') ? 'zh' : 'en'

  const [sql, setSql] = useState('')
  const [dialect, setDialect] = useState('hive')
  const [mode, setMode] = useState<'static' | 'agent'>('static')
  const [ddl, setDdl] = useState('')
  const [rulesText, setRulesText] = useState('')

  const sqlRef = useRef<HTMLTextAreaElement>(null)

  const [reviewing, setReviewing] = useState(false)
  const [fixing, setFixing] = useState(false)
  const [report, setReport] = useState('')
  const [fixedSql, setFixedSql] = useState('')
  const [error, setError] = useState('')

  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [statsError, setStatsError] = useState('')

  const loadStats = () => {
    setStatsError('')
    fetchStats()
      .then(setStats)
      .catch((e) => setStatsError(`${e instanceof Error ? e.message : e}`))
  }

  // URL prefill: /sqlreview?sql=...&dialect=... (used by the Text2SQL
  // inline review card's "full review" link)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const urlSql = (params.get('sql') || '').trim()
    if (urlSql) setSql(urlSql.slice(0, 20000))
    const raw = (params.get('dialect') || '').trim().toLowerCase()
    const urlDialect = DIALECT_ALIASES[raw] ?? raw
    if ((DIALECTS as readonly string[]).includes(urlDialect)) setDialect(urlDialect)
  }, [])

  // report locations link to #srline-N: select + scroll to that SQL line
  const jumpToLine = (line: number) => {
    const box = sqlRef.current
    if (!box) return
    const rows = box.value.split('\n')
    if (line > rows.length) return
    let start = 0
    for (let i = 0; i < line - 1; i++) start += rows[i].length + 1
    box.focus()
    box.setSelectionRange(start, start + rows[line - 1].length)
    const lh = parseFloat(getComputedStyle(box).lineHeight) || 20
    box.scrollTop = Math.max(0, (line - 3) * lh)
    box.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  // hand the current SQL to the transpile / data-skew pages via localStorage
  // (survives the new tab; query params would hit the header-size cap)
  const sendTo = (storageKey: string, route: string) => {
    if (!sql.trim()) return
    localStorage.setItem(storageKey, sql)
    window.open(route, '_blank')
  }

  // YAML rules → inline dict for the API (the legacy page parsed server-side)
  const parseRules = (): Record<string, unknown> | undefined => {
    const text = rulesText.trim()
    if (!text) return undefined
    const parsed = parseYaml(text)
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('rules must be a YAML mapping (key: value)')
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
        line_links: true,
        source: 'ui',
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
      // static mode's "nothing mechanically fixable" comes back as 422
      if (e instanceof ApiError && e.status === 422 && mode === 'static') {
        setFixedSql(t('fixNoneStatic'))
      } else {
        setFixedSql(`${t('fixFailed')}: ${e instanceof Error ? e.message : e}`)
      }
    } finally {
      setFixing(false)
    }
  }

  // DDL / rules survive Clear, matching the legacy page (they are session
  // context the user set up, not per-review input)
  const onClear = () => {
    setSql('')
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
          ref={sqlRef}
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
            <button
              onClick={() => sendTo('st_transpile_sql', '/transpile')}
              className="rounded border-[1.5px] border-line px-3 py-2 font-mono text-[13px] text-muted transition hover:border-ink hover:text-ink"
            >
              {t('transpileBtn')}
            </button>
            <button
              onClick={() => sendTo('st_dataskew_sql', '/dataskew')}
              className="rounded border-[1.5px] border-line px-3 py-2 font-mono text-[13px] text-muted transition hover:border-ink hover:text-ink"
            >
              {t('skewBtn')}
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
            <ReportView markdown={report} onLineClick={jumpToLine} />
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
      <section className="mt-8">
        <Collapsible title={t('statsAccordion')} onOpen={loadStats}>
          <div className="flex items-start justify-between gap-4">
            <div className="font-mono text-sm text-fg">
              {statsError && <p className="text-[var(--accent)]">{statsError}</p>}
              {!stats && !statsError && <p className="italic text-muted">{t('statsPlaceholder')}</p>}
              {stats && stats.summary.reviews === 0 && (
                <p className="text-muted">{t('noRecords')}</p>
              )}
              {stats && stats.summary.reviews > 0 && (
                <>
                  <div className="flex flex-wrap gap-x-5 gap-y-1">
                    <span className="text-muted">
                      {t('statReviews')} <b className="text-fg">{stats.summary.reviews}</b>
                    </span>
                    <span className="text-muted">
                      {t('statFindings')} <b className="text-fg">{stats.summary.findings}</b>
                    </span>
                    {(['critical', 'risk', 'suggestion'] as const).map((sev) => (
                      <span key={sev} className="text-muted">
                        {t(`sev_${sev}`)}{' '}
                        <b className="text-fg">{stats.summary.severities[sev] ?? 0}</b>
                      </span>
                    ))}
                  </div>
                  {stats.summary.top_categories.length > 0 && (
                    <div className="mt-3">
                      <p className="font-bold text-ink">{t('topCategories')}</p>
                      <ul className="mt-1 list-disc pl-5 text-muted">
                        {stats.summary.top_categories.slice(0, 5).map((c) => (
                          <li key={c.category || c.label}>
                            {categoryLabel(c, lang)} ({c.count})
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>
            <button
              onClick={loadStats}
              className="shrink-0 rounded border-[1.5px] border-ink px-3 py-1.5 font-mono text-[13px] text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
            >
              {t('refresh')}
            </button>
          </div>
          {stats && stats.daily.length > 0 && (
            <div className="mt-4">
              <TrendChart daily={stats.daily} />
            </div>
          )}
        </Collapsible>
      </section>

    </div>
  )
}
