import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { fieldCls, labelCls } from '@shared/constants'
import { analyze } from '@/api'

export default function App() {
  const { t, i18n } = useTranslation()
  const [name, setName] = useState('job')
  const [log, setLog] = useState('')
  const [runs, setRuns] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')

  const runAnalyze = async () => {
    if (!log.trim() && !runs.trim()) {
      setReport('')
      setError(t('empty'))
      return
    }
    setBusy(true)
    setError('')
    try {
      const res = await analyze({
        logs: log.trim() ? [{ name: name.trim() || 'job', text: log }] : [],
        runs_json: runs,
        lang: i18n.language,
      })
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
      setError(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="devops / ci" titlePrefix="🧭" maxW="max-w-[660px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={labelCls}>{t('name_label')}</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              spellCheck={false}
              className={fieldCls}
            />
            <label className={`${labelCls} mt-3 block`}>{t('log_label')}</label>
            <textarea
              value={log}
              onChange={(e) => setLog(e.target.value)}
              placeholder={t('log_ph')}
              rows={10}
              spellCheck={false}
              className={`${fieldCls} resize-y`}
            />
            <details className="mt-3">
              <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                {t('runs_acc')}
              </summary>
              <label className={`${labelCls} mt-2 block`}>{t('runs_label')}</label>
              <textarea
                value={runs}
                onChange={(e) => setRuns(e.target.value)}
                placeholder={t('runs_ph')}
                rows={6}
                spellCheck={false}
                className={`${fieldCls} resize-y`}
              />
            </details>
            <button
              onClick={() => void runAnalyze()}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('analyze_btn')}
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
            {report && <ReportView className="ci-report" markdown={report} />}
            {!report && !error && <p className="text-sm text-muted">{t('report_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
