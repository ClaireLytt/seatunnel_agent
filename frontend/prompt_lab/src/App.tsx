import { useEffect, useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { ACTIVE, fetchProfiles, runMatrix } from '@/api'
import { Card } from '@shared/components/card'
import { ReportView } from '@shared/components/ReportView'
import { labelCls, textareaCls } from '@shared/constants'

export default function App() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language.startsWith('zh') ? 'zh' : 'en'

  const [prompt, setPrompt] = useState('')
  const [system, setSystem] = useState('')
  const [profiles, setProfiles] = useState<string[]>([ACTIVE])
  const [selected, setSelected] = useState<string[]>([ACTIVE])
  const [parallel, setParallel] = useState(true)
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState('')

  useEffect(() => {
    fetchProfiles()
      .then(setProfiles)
      .catch(() => setProfiles([ACTIVE]))
  }, [])

  const toggleProfile = (name: string, checked: boolean) => {
    setSelected((prev) => (checked ? [...prev, name] : prev.filter((p) => p !== name)))
  }

  const onRun = async () => {
    // Local gate — mirrors the Gradio page's do_run: no request is sent.
    if (!prompt.trim()) {
      setReport(t('emptyPrompt'))
      return
    }
    if (selected.length === 0) {
      setReport(t('noProfiles'))
      return
    }
    setRunning(true)
    try {
      const r = await runMatrix(prompt, system, selected, parallel, lang)
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
            ai / promptlab
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
          <label className={labelCls} htmlFor="prompt">
            {t('promptLabel')}
          </label>
          <textarea
            id="prompt"
            className={`${textareaCls} min-h-[160px]`}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={t('promptPh')}
          />

          <label className={`${labelCls} mt-4`} htmlFor="system">
            {t('systemLabel')}
          </label>
          <textarea
            id="system"
            className={`${textareaCls} min-h-[64px]`}
            value={system}
            onChange={(e) => setSystem(e.target.value)}
            placeholder={t('systemPh')}
          />

          <fieldset className="mt-4">
            <legend className={labelCls}>{t('profilesLabel')}</legend>
            <div className="mt-1 flex flex-col gap-1.5">
              {profiles.map((name) => (
                <label
                  key={name}
                  className="flex items-center gap-2 font-mono text-sm text-fg"
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(name)}
                    onChange={(e) => toggleProfile(name, e.target.checked)}
                    className="h-4 w-4 accent-[var(--ink)]"
                  />
                  {name}
                </label>
              ))}
            </div>
          </fieldset>
          {profiles.length <= 1 && (
            <p className="mt-2 text-xs text-muted">
              <Trans
                i18nKey="profilesHint"
                components={[
                  <a key="settings" href="/settings" className="underline" />,
                ]}
              />
            </p>
          )}

          <label className="mt-4 flex items-center gap-2 font-mono text-sm text-fg">
            <input
              type="checkbox"
              checked={parallel}
              onChange={(e) => setParallel(e.target.checked)}
              className="h-4 w-4 accent-[var(--ink)]"
            />
            {t('parallelLabel')}
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
            <ReportView className="pl-report" markdown={report} />
          ) : (
            <p className="text-muted">{t('reportPh')}</p>
          )}
        </Card>
      </div>
    </div>
  )
}
