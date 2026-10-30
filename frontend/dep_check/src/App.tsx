import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { checkText, checkSelf } from '@/api'

export default function App() {
  const { t, i18n } = useTranslation()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')

  const runCheck = async () => {
    if (!text.trim()) {
      setError(t('empty_text'))
      setReport('')
      return
    }
    setBusy(true)
    setError('')
    try {
      const isPyproject = text.includes('[project]') || text.includes('[build-system]')
      const res = await checkText(isPyproject ? text : '', isPyproject ? '' : text, i18n.language)
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const runSelf = async () => {
    setBusy(true)
    setError('')
    try {
      const res = await checkSelf(i18n.language)
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const clear = () => {
    setText('')
    setError('')
    setReport('')
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="devops / depcheck" titlePrefix="📦" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('text_label')}
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={t('text_ph')}
              rows={12}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <button
              onClick={runCheck}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('check_btn')}
            </button>
            <button
              onClick={runSelf}
              disabled={busy}
              className="mt-2 w-full rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {t('self_btn')}
            </button>
            <button
              onClick={clear}
              disabled={busy}
              className="mt-2 w-full rounded border-[1.5px] border-transparent px-4 py-2 font-mono text-sm text-ink-soft transition hover:border-line disabled:opacity-50"
            >
              {t('clear_btn')}
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
            {report && <ReportView markdown={report} />}
            {!report && !error && <p className="text-sm text-muted">{t('report_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
