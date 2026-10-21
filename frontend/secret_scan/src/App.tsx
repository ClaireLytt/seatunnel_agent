import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
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
      <header className="flex items-start justify-between gap-4">
        <div>
          <span className="mb-3 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            devops / secrets
          </span>
          <h1 className="font-display text-3xl font-bold tracking-tight text-ink">🔑 {t('title')}</h1>
          <p className="mt-2 max-w-[660px] text-sm text-muted">{t('subtitle')}</p>
        </div>
        <a
          href="/"
          title={t('home')}
          className="shrink-0 rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
        >
          {t('home')}
        </a>
      </header>

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
