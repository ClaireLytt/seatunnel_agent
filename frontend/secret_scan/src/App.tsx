import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { fieldCls, labelCls } from '@shared/constants'
import { scan } from '@/api'

export default function App() {
  const { t, i18n } = useTranslation()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')

  const runScan = async () => {
    if (!text.trim()) {
      setReport('')
      setError(t('empty_text'))
      return
    }
    setBusy(true)
    setError('')
    try {
      const res = await scan({ text, lang: i18n.language })
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
      <PageHeader badge="devops / secrets" titlePrefix="🔑" maxW="max-w-[660px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={labelCls}>{t('text_label')}</label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={t('text_ph')}
              rows={12}
              spellCheck={false}
              className={`${fieldCls} resize-y`}
            />
            <button
              onClick={() => void runScan()}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('scan_btn')}
            </button>
          </Card>

          <Card>
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">{t('dir_hint')}</p>
            <code className="mt-2 block rounded bg-[var(--grid)] px-2 py-1 font-mono text-xs text-ink">
              seatunnel-agent secretscan --fail-on high
            </code>
          </Card>
        </aside>

        <main className="min-w-0 flex-1">
          <Card>
            {error && (
              <div className="mb-3 font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {error}
              </div>
            )}
            {report && <ReportView className="secret-report" markdown={report} />}
            {!report && !error && <p className="text-sm text-muted">{t('report_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
