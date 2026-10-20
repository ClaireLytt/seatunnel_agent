import { useState } from 'react'
import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { fetchDemoSuite, fetchHistory, runSuite, validateSuite } from '@/api'
import type { HistoryRun } from '@/api'
import { Card } from '@shared/components/card'
import { ReportView } from '@shared/components/ReportView'
import { labelCls, textareaCls } from '@shared/constants'
import { TrendChart } from '@/TrendChart'

export default function App() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language.startsWith('zh') ? 'zh' : 'en'

  const [suiteYaml, setSuiteYaml] = useState('')
  const [judge, setJudge] = useState(false)
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState('')
  const [trendRuns, setTrendRuns] = useState<HistoryRun[] | null>(null)

  const onLoadDemo = async () => {
    try {
      setSuiteYaml(await fetchDemoSuite())
    } catch (e) {
      setReport(`⚠️ ${e instanceof Error ? e.message : e}`)
    }
  }

  // Parse-only feedback loop — never calls the LLM (mirrors Gradio do_validate).
  const onValidate = async () => {
    if (!suiteYaml.trim()) {
      setReport(t('emptySuite'))
      return
    }
    try {
      const r = await validateSuite(suiteYaml)
      setReport(
        r.ok
          ? t('validOk', { n: r.cases, agents: r.agents.join(', ') })
          : `⚠️ ${r.error}`,
      )
    } catch (e) {
      setReport(`⚠️ ${e instanceof Error ? e.message : e}`)
    }
  }

  const onRefreshTrend = async () => {
    try {
      setTrendRuns(await fetchHistory(200))
    } catch {
      setTrendRuns([])
    }
  }

  const onRun = async () => {
    if (!suiteYaml.trim()) {
      setReport(t('emptySuite'))
      return
    }
    setRunning(true)
    try {
      const r = await runSuite(suiteYaml, judge, lang)
      setReport(r.report ?? '')
    } catch (e) {
      setReport(`⚠️ ${e instanceof Error ? e.message : e}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-10">
      <motion.header
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex items-start justify-between gap-4"
      >
        <div>
          <span className="mb-4 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            ai / llmeval
          </span>
          <h1 className="font-display text-4xl font-bold tracking-tight text-ink">
            {t('title')}
          </h1>
          <p className="mt-3 max-w-[680px] text-muted">{t('subtitle')}</p>
        </div>
        <a
          href="/"
          title={t('home')}
          className="shrink-0 rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
        >
          {t('home')}
        </a>
      </motion.header>

      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-[2fr_5fr]">
        <Card>
          <label className={labelCls} htmlFor="suite">
            {t('suiteLabel')}
          </label>
          <textarea
            id="suite"
            className={`${textareaCls} min-h-[340px]`}
            value={suiteYaml}
            onChange={(e) => setSuiteYaml(e.target.value)}
            placeholder={t('suitePh')}
          />
          <div className="mt-3 flex gap-2">
            <button
              onClick={onLoadDemo}
              className="flex-1 rounded border-[1.5px] border-ink px-3 py-1.5 font-mono text-xs text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
            >
              {t('demoBtn')}
            </button>
            <button
              onClick={onValidate}
              className="flex-1 rounded border-[1.5px] border-ink px-3 py-1.5 font-mono text-xs text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
            >
              {t('validateBtn')}
            </button>
          </div>
          <label className="mt-4 flex items-center gap-2 font-mono text-sm text-fg">
            <input
              type="checkbox"
              checked={judge}
              onChange={(e) => setJudge(e.target.checked)}
              className="h-4 w-4 accent-[var(--ink)]"
            />
            {t('judgeLabel')}
          </label>
          <button
            onClick={onRun}
            disabled={running}
            className="mt-4 w-full rounded border-[1.5px] border-ink bg-ink px-6 py-2 font-mono text-sm text-paper transition enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard disabled:opacity-50"
          >
            {running ? t('running') : t('runBtn')}
          </button>
        </Card>

        <Card>
          {running ? (
            <p className="font-mono text-sm text-muted">{t('running')}</p>
          ) : report ? (
            <ReportView className="le-report" markdown={report} />
          ) : (
            <p className="text-muted">{t('reportPh')}</p>
          )}

          <details className="mt-6 rounded border border-line">
            <summary className="cursor-pointer select-none px-3 py-2 font-mono text-sm text-ink">
              {t('trendAcc')}
            </summary>
            <div className="px-3 pb-3">
              {trendRuns !== null &&
                (trendRuns.length > 0 ? (
                  <TrendChart runs={trendRuns} />
                ) : (
                  <p className="font-mono text-sm text-muted">{t('noRuns')}</p>
                ))}
              <button
                onClick={onRefreshTrend}
                className="mt-2 rounded border-[1.5px] border-ink px-3 py-1.5 font-mono text-xs text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
              >
                {t('trendBtn')}
              </button>
            </div>
          </details>
        </Card>
      </div>
    </div>
  )
}
