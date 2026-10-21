import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ask } from '@/api'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { btnPrimary, labelCls, textareaCls } from '@shared/constants'
import { langOf } from '@shared/lang'
import { useRunner } from '@shared/useRunner'

export default function App() {
  const { t, i18n } = useTranslation()
  const lang = langOf(i18n)

  const [question, setQuestion] = useState('')
  const [useLlm, setUseLlm] = useState(false)
  const { busy, error, result, run, setError } = useRunner(ask)

  const onAsk = () => {
    // Local gate — mirrors the Gradio page's do_ask: no request is sent.
    if (!question.trim()) {
      setError(t('empty'))
      return
    }
    void run(question, useLlm, lang)
  }

  const report = error || (result?.markdown ?? '')

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-10">
      <PageHeader badge="ai / docqa" />

      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-[2fr_5fr]">
        <Card>
          <label className={labelCls} htmlFor="question">
            {t('qLabel')}
          </label>
          <textarea
            id="question"
            rows={4}
            className={textareaCls}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              // Enter submits, Shift+Enter inserts a newline — like the
              // Gradio Textbox's submit event.
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (!busy) onAsk()
              }
            }}
            placeholder={t('qPh')}
          />

          <label className="mt-4 flex items-center gap-2 font-mono text-sm text-fg">
            <input
              type="checkbox"
              checked={useLlm}
              onChange={(e) => setUseLlm(e.target.checked)}
              className="h-4 w-4 accent-[var(--ink)]"
            />
            {t('llmLabel')}
          </label>

          <button onClick={onAsk} disabled={busy} className={btnPrimary}>
            {busy ? t('running') : t('askBtn')}
          </button>
        </Card>

        <Card>
          {busy ? (
            <p className="font-mono text-sm text-muted">{t('running')}</p>
          ) : report ? (
            <ReportView className="dq-report" markdown={report} />
          ) : (
            <p className="text-muted">{t('reportPh')}</p>
          )}
        </Card>
      </div>
    </div>
  )
}
