import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { runTriage } from '@/api'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { btnPrimary, fieldCls, labelCls, textareaCls } from '@shared/constants'
import { langOf } from '@shared/lang'
import { useRunner } from '@shared/useRunner'

export default function App() {
  const { t, i18n } = useTranslation()
  const lang = langOf(i18n)

  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const { busy, error, result, run, setError } = useRunner(runTriage)

  const onTriage = () => {
    // Local gate — mirrors the Gradio page's do_triage: no request is sent.
    if (!title.trim()) {
      setError(t('empty'))
      return
    }
    void run(title, body, lang)
  }

  const report = error || (result?.report ?? '')

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-10">
      <PageHeader badge="ai / triage" />

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

          <button onClick={onTriage} disabled={busy} className={btnPrimary}>
            {busy ? t('running') : t('runBtn')}
          </button>
        </Card>

        <Card>
          {busy ? (
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
