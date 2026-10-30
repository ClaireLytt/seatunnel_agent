import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { langOf } from '@shared/lang'
import { runTask } from '@/api'
import type { DoneEvent } from '@/api'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { fieldCls, labelCls, textareaCls } from '@shared/constants'

/** Pull the FastAPI `detail` out of a postSSE error body when present. */
function errorText(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e)
  const m = msg.match(/^HTTP (\d+) (.*)$/s)
  if (m) {
    try {
      const detail = (JSON.parse(m[2]) as { detail?: string }).detail
      if (detail) return `HTTP ${m[1]} — ${detail}`
    } catch {
      /* not JSON — fall through */
    }
  }
  return msg
}

export default function App() {
  const { t, i18n } = useTranslation()
  const lang = langOf(i18n)

  const [goal, setGoal] = useState('')
  const [url, setUrl] = useState('http://127.0.0.1:7860/')
  const [maxSteps, setMaxSteps] = useState(15)
  const [running, setRunning] = useState(false)

  // Report area: streamed step lines, then a terminal result / error / notice.
  const [stepLines, setStepLines] = useState<string[]>([])
  const [result, setResult] = useState<DoneEvent | null>(null)
  const [notice, setNotice] = useState('')

  const onRun = async () => {
    // Local gate — mirrors the Gradio do_run: empty goal/URL sends no request.
    if (!goal.trim() || !url.trim()) {
      setStepLines([])
      setResult(null)
      setNotice(t('empty'))
      return
    }
    setRunning(true)
    setStepLines([])
    setResult(null)
    setNotice('')
    let i = 0
    try {
      await runTask({ goal: goal.trim(), url: url.trim(), max_steps: maxSteps, lang }, (e) => {
        if (e.type === 'step') {
          i += 1
          const line = t('stepLine', {
            i,
            tool: e.tool,
            ms: e.elapsed_ms,
            err: e.error ? ' · !' : '',
          })
          setStepLines((prev) => [...prev, line])
        } else if (e.type === 'done') {
          setResult(e)
        } else {
          setNotice(`${e.message}`)
        }
      })
    } catch (e) {
      setNotice(`${errorText(e)}`)
    } finally {
      setRunning(false)
    }
  }

  const empty = !running && stepLines.length === 0 && !result && !notice

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-10">
      <PageHeader badge="ai / webtask" titlePrefix="🖱️" />

      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-[2fr_5fr]">
        <Card>
          <label className={labelCls} htmlFor="goal">
            {t('goalLabel')}
          </label>
          <textarea
            id="goal"
            className={`${textareaCls} min-h-[88px]`}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder={t('goalPh')}
          />

          <label className={`${labelCls} mt-4`} htmlFor="url">
            {t('urlLabel')}
          </label>
          <input
            id="url"
            type="text"
            className={fieldCls}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />

          <label className={`${labelCls} mt-4`} htmlFor="steps">
            {t('stepsLabel')}
            <span className="ml-2 normal-case tracking-normal text-ink">{maxSteps}</span>
          </label>
          <input
            id="steps"
            type="range"
            min={4}
            max={25}
            step={1}
            value={maxSteps}
            onChange={(e) => setMaxSteps(Number(e.target.value))}
            className="w-full accent-[var(--ink)]"
          />

          <button
            onClick={onRun}
            disabled={running}
            className="mt-4 w-full rounded border-[1.5px] border-ink bg-ink px-6 py-2 font-mono text-sm text-paper transition enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard disabled:opacity-50"
          >
            {running ? t('running') : t('runBtn')}
          </button>
        </Card>

        <Card>
          {empty && <p className="text-muted">{t('reportPh')}</p>}

          {stepLines.length > 0 && (
            <ol className="flex flex-col gap-1.5 font-mono text-[13px] text-fg">
              {stepLines.map((line, idx) => (
                <li key={idx}>{line}</li>
              ))}
            </ol>
          )}

          {notice && <p className="mt-2 font-mono text-sm text-fg">{notice}</p>}

          {result && (
            <div className="mt-4 border-t border-line pt-4">
              <h2 className="font-display text-xl font-bold text-ink">
                {result.success ? t('ok') : t('fail')}
              </h2>
              <p className="mt-1 font-mono text-xs text-muted">
                {result.steps.length} steps · {result.elapsed_ms} ms
              </p>
              {result.truncated && (
                <p className="mt-2 border-l-[3px] border-line pl-3 font-mono text-sm text-muted">
                  {t('truncated')}
                </p>
              )}

              {result.reply && (
                <>
                  <h3 className={`${labelCls} mt-5`}>{t('reply')}</h3>
                  <ReportView className="wt-report" markdown={result.reply} />
                </>
              )}

              <h3 className={`${labelCls} mt-5`}>{t('steps')}</h3>
              <ol className="flex flex-col gap-1 font-mono text-xs text-fg">
                {result.steps.map((s, idx) => (
                  <li key={idx}>
                    {idx + 1}. {s.error ? '' : ''}
                    <code>{s.tool}</code> · {s.elapsed_ms} ms
                  </li>
                ))}
              </ol>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
