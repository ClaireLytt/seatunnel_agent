import { useState } from 'react'
import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { fetchDemoSuite, fetchHistory, runSuite, validateSuite } from '@/api'
import type { HistoryRun } from '@/api'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { btnPrimary, labelCls, textareaCls } from '@shared/constants'
import { langOf } from '@shared/lang'
import { useRunner } from '@shared/useRunner'
import { TrendChart } from '@/TrendChart'

export default function App() {
  const { t, i18n } = useTranslation()
  const lang = langOf(i18n)

  const [suiteYaml, setSuiteYaml] = useState('')
  const [judge, setJudge] = useState(false)
  const { busy, error, result, run, setError } = useRunner(runSuite)
  const [trendRuns, setTrendRuns] = useState<HistoryRun[] | null>(null)

  const onLoadDemo = async () => {
    try {
      setSuiteYaml(await fetchDemoSuite())
    } catch (e) {
      setError(`⚠️ ${e instanceof Error ? e.message : e}`)
    }
  }

  // Parse-only feedback loop — never calls the LLM (mirrors Gradio do_validate).
  // Validation outcomes reuse the runner's error slot (same report area).
  const onValidate = async () => {
    if (!suiteYaml.trim()) {
      setError(t('emptySuite'))
      return
    }
    try {
      const r = await validateSuite(suiteYaml)
      setError(
        r.ok
          ? t('validOk', { n: r.cases, agents: r.agents.join(', ') })
          : `⚠️ ${r.error}`,
      )
    } catch (e) {
      setError(`⚠️ ${e instanceof Error ? e.message : e}`)
    }
  }

  const onRefreshTrend = async () => {
    try {
      setTrendRuns(await fetchHistory(200))
    } catch {
      setTrendRuns([])
    }
  }

  const onRun = () => {
    if (!suiteYaml.trim()) {
      setError(t('emptySuite'))
      return
    }
    void run(suiteYaml, judge, lang)
  }

  const report = error || (result?.report ?? '')

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-10">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <PageHeader badge="ai / llmeval" />
      </motion.div>

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
          <button onClick={onRun} disabled={busy} className={btnPrimary}>
            {busy ? t('running') : t('runBtn')}
          </button>
        </Card>

        <Card>
          {busy ? (
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
