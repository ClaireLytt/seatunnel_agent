import { useState } from 'react'
import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { runSuite } from '@/api'
import { Card } from '@shared/components/card'
import { ReportView } from '@shared/components/ReportView'
import { labelCls, textareaCls } from '@shared/constants'

export default function App() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language.startsWith('zh') ? 'zh' : 'en'

  const [suiteYaml, setSuiteYaml] = useState('')
  const [judge, setJudge] = useState(false)
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState('')

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
        </Card>
      </div>
    </div>
  )
}
