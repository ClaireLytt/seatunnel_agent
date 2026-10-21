import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { runTriage } from '@/api'
import { Card } from '@shared/components/card'
import { ReportView } from '@shared/components/ReportView'
import { fieldCls, labelCls, textareaCls } from '@shared/constants'

export default function App() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language.startsWith('zh') ? 'zh' : 'en'

  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState('')

  const onTriage = async () => {
    // Local gate — mirrors the Gradio page's do_triage: no request is sent.
    if (!title.trim()) {
      setReport(t('empty'))
      return
    }
    setRunning(true)
    try {
      const r = await runTriage(title, body, lang)
      setReport(r.report ?? '')
    } catch (e) {
      setReport(`⚠️ ${e instanceof Error ? e.message : e}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-10">
      <header className="flex items-start justify-between gap-4">
        <div>
          <span className="mb-4 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            ai / triage
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
      </header>

      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-[2fr_5fr]">
        <Card>
          <label className={labelCls} htmlFor="issue-title">
            {t('tLabel')}
          </label>
          <input
            id="issue-title"
            type="text"
            className={fieldCls}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />

          <label className={`${labelCls} mt-4`} htmlFor="issue-body">
            {t('bLabel')}
          </label>
          <textarea
            id="issue-body"
            rows={8}
            className={textareaCls}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />

          <button
            onClick={onTriage}
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
            <ReportView className="it-report" markdown={report} />
          ) : (
            <p className="text-muted">{t('reportPh')}</p>
          )}
        </Card>
      </div>
    </div>
  )
}
