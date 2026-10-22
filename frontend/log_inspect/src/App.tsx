import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { scanDir, scanText, getAdvice } from '@/api'

export default function App() {
  const { t, i18n } = useTranslation()
  const [dir, setDir] = useState('examples/logs_demo')
  const [text, setText] = useState('')
  const [includeWarn, setIncludeWarn] = useState(true)
  const [top, setTop] = useState(10)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')
  const [advice, setAdvice] = useState('')
  const [lastDir, setLastDir] = useState<string | null>(null)
  const [lastText, setLastText] = useState<string | null>(null)

  const runScanDir = async () => {
    if (!dir.trim()) {
      setError(t('empty_dir'))
      setReport('')
      return
    }
    setBusy(true)
    setError('')
    setAdvice('')
    try {
      const res = await scanDir(dir.trim(), includeWarn, top, i18n.language)
      setReport(res.report ?? '')
      setLastDir(dir.trim())
      setLastText(null)
    } catch (e) {
      setReport('')
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const runScanText = async () => {
    if (!text.trim()) {
      setError(t('empty_text'))
      setReport('')
      return
    }
    setBusy(true)
    setError('')
    setAdvice('')
    try {
      const res = await scanText(text, includeWarn, top, i18n.language)
      setReport(res.report ?? '')
      setLastDir(null)
      setLastText(text)
    } catch (e) {
      setReport('')
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const runAdvice = async () => {
    if (!lastDir && !lastText) {
      setAdvice(t('advice_none'))
      return
    }
    setBusy(true)
    try {
      const res = await getAdvice(lastDir, lastText, includeWarn, top, i18n.language)
      setAdvice(res.advice)
    } catch (e) {
      setAdvice(String(e))
    } finally {
      setBusy(false)
    }
  }

  const clear = () => {
    setDir('examples/logs_demo')
    setText('')
    setError('')
    setReport('')
    setAdvice('')
    setLastDir(null)
    setLastText(null)
  }

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / loginspect" titlePrefix="🧾" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('dir_label')}
            </label>
            <input
              value={dir}
              onChange={(e) => setDir(e.target.value)}
              placeholder={t('dir_ph')}
              spellCheck={false}
              className="w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <button
              onClick={runScanDir}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('scan_btn')}
            </button>

            <label className="mt-3 flex items-center gap-2 font-mono text-[13px] text-ink-soft">
              <input
                type="checkbox"
                checked={includeWarn}
                onChange={(e) => setIncludeWarn(e.target.checked)}
                className="accent-ink"
              />
              {t('warn_label')}
            </label>

            <label className="mt-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('top_label')}: {top}
            </label>
            <input
              type="range"
              min={3}
              max={50}
              value={top}
              onChange={(e) => setTop(Number(e.target.value))}
              className="w-full accent-ink"
            />

            <button
              onClick={clear}
              disabled={busy}
              className="mt-2 w-full rounded border-[1.5px] border-transparent px-4 py-2 font-mono text-sm text-ink-soft transition hover:border-line disabled:opacity-50"
            >
              {t('clear_btn')}
            </button>
          </Card>

          <Card>
            <details>
              <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                {t('text_acc')}
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                <label className="block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                  {t('text_label')}
                </label>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={t('text_ph')}
                  rows={8}
                  spellCheck={false}
                  className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
                />
                <button
                  onClick={runScanText}
                  disabled={busy}
                  className="w-full rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
                >
                  {t('scan_text_btn')}
                </button>
              </div>
            </details>
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

          {report && (
            <Card>
              <details>
                <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                  {t('advice_acc')}
                </summary>
                <div className="mt-3">
                  <button
                    onClick={runAdvice}
                    disabled={busy}
                    className="rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
                  >
                    {t('advice_btn')}
                  </button>
                  {advice && (
                    <div className="mt-3">
                      <ReportView markdown={advice} />
                    </div>
                  )}
                </div>
              </details>
            </Card>
          )}
        </main>
      </div>
    </div>
  )
}
