import { useEffect, useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { ACTIVE, diffCells, fetchHistory, fetchProfiles, runMatrix } from '@/api'
import type { Cell, HistoryRun } from '@/api'
import { Card } from '@shared/components/card'
import { ReportView } from '@shared/components/ReportView'
import { fieldCls, labelCls, smallBtnCls, textareaCls } from '@shared/constants'

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

  // Diff over the last run's successful cells — mirrors the Gradio page's
  // matrix_state + diff_a/diff_b dropdowns.
  const [okCells, setOkCells] = useState<Cell[]>([])
  const [diffA, setDiffA] = useState('')
  const [diffB, setDiffB] = useState('')
  const [diffMd, setDiffMd] = useState('')

  const [history, setHistory] = useState<HistoryRun[] | null>(null)

  const refreshHistory = () => {
    fetchHistory()
      .then(setHistory)
      .catch(() => setHistory([]))
  }

  useEffect(() => {
    fetchProfiles()
      .then(setProfiles)
      .catch(() => setProfiles([ACTIVE]))
    // Preload the history on page load, like the Gradio page's _on_load.
    refreshHistory()
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
      // Same as the Gradio do_run: diff candidates = cells without error,
      // preselect the first two.
      const ok = r.cells.filter((c) => !c.error)
      setOkCells(ok)
      setDiffA(ok[0]?.profile ?? '')
      setDiffB(ok[1]?.profile ?? '')
    } catch (e) {
      setReport(`⚠️ ${e instanceof Error ? e.message : e}`)
      setOkCells([])
      setDiffA('')
      setDiffB('')
    } finally {
      setRunning(false)
    }
  }

  const onDiff = async () => {
    const a = okCells.find((c) => c.profile === diffA)
    const b = okCells.find((c) => c.profile === diffB)
    if (!a || !b) {
      setDiffMd(t('needTwo'))
      return
    }
    try {
      setDiffMd(
        await diffCells(
          { profile: a.profile, model: a.model, reply: a.reply },
          { profile: b.profile, model: b.model, reply: b.reply },
          lang,
        ),
      )
    } catch (e) {
      setDiffMd(`⚠️ ${e instanceof Error ? e.message : e}`)
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

          <details className="mt-6 rounded border border-line">
            <summary className="cursor-pointer select-none px-3 py-2 font-mono text-sm text-ink">
              {t('diffAcc')}
            </summary>
            <div className="px-3 pb-3">
              <div className="flex flex-wrap items-end gap-3">
                <label className="flex-1 min-w-[140px]">
                  <span className={labelCls}>{t('diffA')}</span>
                  <select
                    className={fieldCls}
                    value={diffA}
                    onChange={(e) => setDiffA(e.target.value)}
                  >
                    <option value="" />
                    {okCells.map((c) => (
                      <option key={c.profile} value={c.profile}>
                        {c.profile}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex-1 min-w-[140px]">
                  <span className={labelCls}>{t('diffB')}</span>
                  <select
                    className={fieldCls}
                    value={diffB}
                    onChange={(e) => setDiffB(e.target.value)}
                  >
                    <option value="" />
                    {okCells.map((c) => (
                      <option key={c.profile} value={c.profile}>
                        {c.profile}
                      </option>
                    ))}
                  </select>
                </label>
                <button onClick={onDiff} className={smallBtnCls}>
                  {t('diffBtn')}
                </button>
              </div>
              {diffMd && (
                <div className="mt-3">
                  <ReportView className="pl-report" markdown={diffMd} />
                </div>
              )}
            </div>
          </details>

          <details className="mt-4 rounded border border-line">
            <summary className="cursor-pointer select-none px-3 py-2 font-mono text-sm text-ink">
              {t('histAcc')}
            </summary>
            <div className="px-3 pb-3">
              {history !== null &&
                (history.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse font-mono text-xs text-fg">
                      <thead>
                        <tr className="border-b border-line text-left text-ink-soft">
                          <th className="py-1.5 pr-3">{t('histTime')}</th>
                          <th className="py-1.5 pr-3">{t('histPrompt')}</th>
                          <th className="py-1.5 pr-3">{t('histProfiles')}</th>
                          <th className="py-1.5">{t('histCells')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...history].reverse().map((r, i) => {
                          const cells = r.cells ?? []
                          const ok = cells.filter((c) => !c.error).length
                          return (
                            <tr key={i} className="border-b border-line">
                              <td className="py-1.5 pr-3 whitespace-nowrap">
                                {(r.ts ?? '').slice(0, 16)}
                              </td>
                              <td className="py-1.5 pr-3">
                                {(r.prompt_preview ?? '').slice(0, 60)}
                              </td>
                              <td className="py-1.5 pr-3">
                                {cells.map((c) => c.profile ?? '?').join(', ')}
                              </td>
                              <td className="py-1.5 whitespace-nowrap">
                                {ok}/{cells.length} ✓
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="font-mono text-sm text-muted">{t('noHistory')}</p>
                ))}
              <button onClick={refreshHistory} className={`${smallBtnCls} mt-2`}>
                {t('histBtn')}
              </button>
            </div>
          </details>
        </Card>
      </div>
    </div>
  )
}
