import { useEffect, useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { ACTIVE, diffCells, fetchHistory, fetchProfiles, runMatrix } from '@/api'
import type { HistoryRun } from '@/api'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { btnPrimary, fieldCls, labelCls, smallBtnCls, textareaCls } from '@shared/constants'
import { langOf } from '@shared/lang'
import { useRunner } from '@shared/useRunner'

export default function App() {
  const { t, i18n } = useTranslation()
  const lang = langOf(i18n)

  const [prompt, setPrompt] = useState('')
  const [system, setSystem] = useState('')
  const [profiles, setProfiles] = useState<string[]>([ACTIVE])
  const [selected, setSelected] = useState<string[]>([ACTIVE])
  const [parallel, setParallel] = useState(true)
  const { busy, error, result, run, setError } = useRunner(runMatrix)

  // Diff over the last run's successful cells — mirrors the Gradio page's
  // matrix_state + diff_a/diff_b dropdowns (cells without error).
  const okCells = result ? result.cells.filter((c) => !c.error) : []
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

  // Same as the Gradio do_run: preselect the first two diff candidates after
  // each run; a failed run (result = null) clears both.
  useEffect(() => {
    const ok = result ? result.cells.filter((c) => !c.error) : []
    setDiffA(ok[0]?.profile ?? '')
    setDiffB(ok[1]?.profile ?? '')
  }, [result])

  const toggleProfile = (name: string, checked: boolean) => {
    setSelected((prev) => (checked ? [...prev, name] : prev.filter((p) => p !== name)))
  }

  const onRun = () => {
    // Local gate — mirrors the Gradio page's do_run: no request is sent.
    if (!prompt.trim()) {
      setError(t('emptyPrompt'))
      return
    }
    if (selected.length === 0) {
      setError(t('noProfiles'))
      return
    }
    void run(prompt, system, selected, parallel, lang)
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
      setDiffMd(`${e instanceof Error ? e.message : e}`)
    }
  }

  const report = error || (result?.report ?? '')

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-10">
      <PageHeader badge="ai / promptlab" />

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
                <label key={name} className="flex items-center gap-2 font-mono text-sm text-fg">
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
                components={[<a key="settings" href="/settings" className="underline" />]}
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

          <button onClick={onRun} disabled={busy} className={btnPrimary}>
            {busy ? t('running') : t('runBtn')}
          </button>
        </Card>

        <Card>
          {busy ? (
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
