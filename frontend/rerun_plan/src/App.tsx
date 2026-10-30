import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { ApiError, runPlan } from '@/api'

export default function App() {
  const { t, i18n } = useTranslation()
  const [file, setFile] = useState('examples/rerun_demo/dag.json')
  const [failed, setFailed] = useState('clean_orders')
  const [succeeded, setSucceeded] = useState('')
  const [cmd, setCmd] = useState('')
  const [llm, setLlm] = useState(false)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [report, setReport] = useState('')

  const run = async (useText: boolean) => {
    const src = useText ? text : file
    if (!src.trim()) {
      setError(t('empty_input'))
      setReport('')
      return
    }
    if (!failed.trim()) {
      setError(t('empty_failed'))
      setReport('')
      return
    }
    setBusy(true)
    setError('')
    try {
      const res = await runPlan(
        useText ? null : file.trim(),
        useText ? text : null,
        failed.trim(),
        succeeded,
        cmd,
        i18n.language,
        llm,
      )
      setReport(res.report ?? '')
    } catch (e) {
      setReport('')
      if (e instanceof ApiError && e.code === 'bad_dir') {
        setError(t('bad_dir') + e.path)
      } else {
        setError(String(e))
      }
    } finally {
      setBusy(false)
    }
  }

  const clear = () => {
    setFile('examples/rerun_demo/dag.json')
    setFailed('clean_orders')
    setSucceeded('')
    setCmd('')
    setLlm(false)
    setText('')
    setError('')
    setReport('')
  }

  const inputCls =
    'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'
  const labelCls = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / rerun" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={labelCls}>{t('file_label')}</label>
            <input
              value={file}
              onChange={(e) => setFile(e.target.value)}
              placeholder={t('file_ph')}
              spellCheck={false}
              className={inputCls}
            />
            <label className={`${labelCls} mt-3`}>{t('failed_label')}</label>
            <input
              value={failed}
              onChange={(e) => setFailed(e.target.value)}
              placeholder={t('failed_ph')}
              spellCheck={false}
              className={inputCls}
            />
            <label className={`${labelCls} mt-3`}>{t('ok_label')}</label>
            <input
              value={succeeded}
              onChange={(e) => setSucceeded(e.target.value)}
              placeholder={t('ok_ph')}
              spellCheck={false}
              className={inputCls}
            />
            <label className={`${labelCls} mt-3`}>{t('cmd_label')}</label>
            <input
              value={cmd}
              onChange={(e) => setCmd(e.target.value)}
              placeholder={t('cmd_ph')}
              spellCheck={false}
              className={inputCls}
            />
            <label className="mt-3 flex cursor-pointer items-center gap-2 font-mono text-[12px] text-ink-soft">
              <input type="checkbox" checked={llm} onChange={(e) => setLlm(e.target.checked)} />
              {t('llm_label')}
            </label>
            <button
              onClick={() => run(false)}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : t('run_btn')}
            </button>
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
                <label className={labelCls}>{t('text_label')}</label>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={t('text_ph')}
                  rows={8}
                  spellCheck={false}
                  className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
                />
                <button
                  onClick={() => run(true)}
                  disabled={busy}
                  className="w-full rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
                >
                  {t('run_text_btn')}
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
        </main>
      </div>
    </div>
  )
}
