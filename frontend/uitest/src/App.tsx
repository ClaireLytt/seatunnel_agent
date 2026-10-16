import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import {
  fetchMeta,
  fetchRuns,
  reportDownloadUrl,
  reportUrl,
  runSuite,
  saveCase,
  type Meta,
  type RunCounts,
  type RunEntry,
} from '@/api'
import { CountsChart } from '@/components/CountsChart'
import { Card } from '@/components/ui/card'

const inputCls =
  'w-full rounded border border-line bg-card px-3 py-2 font-mono text-sm text-fg ' +
  'outline-none focus:border-ink'

const labelCls = 'mb-1 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

export default function App() {
  const { t, i18n } = useTranslation()
  const zh = i18n.language.startsWith('zh')

  const [meta, setMeta] = useState<Meta | null>(null)
  const [suite, setSuite] = useState('smoke')
  const [agent, setAgent] = useState('all')
  const [caseIds, setCaseIds] = useState('')
  const [noLlm, setNoLlm] = useState(true)

  const [running, setRunning] = useState(false)
  const [lines, setLines] = useState<string[]>([])
  const [counts, setCounts] = useState<RunCounts | null>(null)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [runId, setRunId] = useState('')
  const progressRef = useRef<HTMLPreElement>(null)

  const [history, setHistory] = useState<RunEntry[]>([])

  const [caseYaml, setCaseYaml] = useState('')
  const [caseStatus, setCaseStatus] = useState('')
  const [editorOpen, setEditorOpen] = useState(false)

  useEffect(() => {
    fetchMeta()
      .then(setMeta)
      .catch((e) => setLines([`❌ ${e}`]))
    fetchRuns().then(setHistory).catch(console.error)
  }, [])

  useEffect(() => {
    progressRef.current?.scrollTo(0, progressRef.current.scrollHeight)
  }, [lines])

  const onRun = async () => {
    setRunning(true)
    setLines([t('starting')])
    setCounts(null)
    setRunId('')
    try {
      await runSuite({ suite, agent, case_ids: caseIds, no_llm: noLlm }, (e) => {
        if (e.type === 'progress') setLines((ls) => [...ls, e.line])
        else if (e.type === 'error') setLines((ls) => [...ls, '', `❌ ${e.message}`])
        else {
          setCounts(e.counts)
          setElapsedMs(e.elapsed_ms)
          setRunId(e.run_id)
        }
      })
    } catch (e) {
      setLines((ls) => [...ls, '', `❌ ${e}`])
    } finally {
      setRunning(false)
      fetchRuns().then(setHistory).catch(console.error)
    }
  }

  const onSaveCase = async () => {
    setCaseStatus('')
    try {
      const r = await saveCase(caseYaml)
      setCaseStatus(`✅ ${t('editorSaved', { ids: r.ids.join(', '), path: r.path })}`)
    } catch (e) {
      setCaseStatus(`❌ ${e instanceof Error ? e.message : e}`)
    }
  }

  return (
    <div className="mx-auto max-w-[1020px] px-4 py-10">
      <motion.header
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex items-start justify-between gap-4"
      >
        <div>
          <span className="mb-4 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            devops / uitest
          </span>
          <h1 className="font-display text-4xl font-bold tracking-tight text-ink">{t('title')}</h1>
          <p className="mt-3 max-w-[620px] text-muted">{t('subtitle')}</p>
        </div>
        <a
          href="/"
          title={t('home')}
          className="shrink-0 rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
        >
          {t('home')}
        </a>
      </motion.header>

      <Card className="mt-8">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_1.2fr_1.6fr_auto_auto]">
          <div>
            <label className={labelCls} htmlFor="suite">
              {t('suite')}
            </label>
            <select
              id="suite"
              className={inputCls}
              value={suite}
              onChange={(e) => setSuite(e.target.value)}
            >
              {(meta?.suites ?? ['smoke']).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls} htmlFor="agent">
              {t('agent')}
            </label>
            <select
              id="agent"
              className={inputCls}
              value={agent}
              onChange={(e) => setAgent(e.target.value)}
            >
              {(meta?.agents ?? []).map((a) => (
                <option key={a.key} value={a.key}>
                  {zh ? a.label_zh : a.label_en}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls} htmlFor="cases">
              {t('cases')}
            </label>
            <input
              id="cases"
              className={inputCls}
              value={caseIds}
              onChange={(e) => setCaseIds(e.target.value)}
              placeholder="A5 B3"
            />
          </div>
          <label className="flex items-end gap-2 pb-2 font-mono text-sm text-fg">
            <input
              type="checkbox"
              checked={noLlm}
              onChange={(e) => setNoLlm(e.target.checked)}
              className="h-4 w-4 accent-[var(--ink)]"
            />
            {t('noLlm')}
          </label>
          <div className="flex items-end">
            <button
              onClick={onRun}
              disabled={running || !meta}
              className="rounded border-[1.5px] border-ink bg-ink px-6 py-2 font-mono text-sm text-paper transition enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard disabled:opacity-50"
            >
              {running ? t('running') : t('run')}
            </button>
          </div>
        </div>
      </Card>

      <AnimatePresence>
        {lines.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6"
          >
            <h2 className="mb-2 font-display text-xl font-bold text-ink">{t('progress')}</h2>
            <pre
              ref={progressRef}
              className="max-h-[320px] overflow-auto whitespace-pre-wrap rounded border border-line bg-card p-4 font-mono text-[13px] leading-6 text-fg"
            >
              {lines.join('\n')}
            </pre>
          </motion.section>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {counts && (
          <motion.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6"
          >
            <h2 className="mb-2 font-display text-xl font-bold text-ink">{t('results')}</h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-[1.2fr_1fr]">
              <Card>
                <CountsChart counts={counts} />
              </Card>
              <Card className="font-mono text-sm">
                <div className="flex flex-wrap gap-x-5 gap-y-1">
                  {['PASS', 'HEALED', 'FAIL', 'ERROR', 'SKIP', 'MANUAL'].map((k) => (
                    <span key={k} className="text-muted">
                      {k} <b className="text-fg">{counts[k] ?? 0}</b>
                    </span>
                  ))}
                </div>
                <div className="mt-2 text-muted">
                  {t('elapsed')} <b className="text-fg">{(elapsedMs / 1000).toFixed(0)}s</b>
                </div>
                {runId && (
                  <a
                    href={reportDownloadUrl(runId)}
                    className="mt-4 inline-block rounded border-[1.5px] border-ink px-4 py-2 text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
                  >
                    {t('download')}
                  </a>
                )}
              </Card>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {runId && (
          <motion.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6"
          >
            <h2 className="mb-2 font-display text-xl font-bold text-ink">{t('report')}</h2>
            <iframe
              title={t('report')}
              src={reportUrl(runId)}
              sandbox="allow-same-origin"
              className="h-[70vh] w-full rounded border border-line bg-card"
            />
          </motion.section>
        )}
      </AnimatePresence>

      {history.length > 0 && (
        <section className="st-history mt-8">
          <h2 className="mb-2 font-display text-xl font-bold text-ink">{t('history')}</h2>
          <Card className="p-0">
            <table className="w-full font-mono text-[13px]">
              <tbody>
                {history.map((h) => (
                  <tr key={h.run_id} className="border-b border-line last:border-b-0">
                    <td className="px-4 py-2 text-fg">{h.run_id}</td>
                    <td className="px-2 py-2 text-muted">{h.suite}</td>
                    <td className="px-2 py-2">
                      {(['PASS', 'HEALED', 'FAIL', 'ERROR', 'SKIP', 'MANUAL'] as const)
                        .filter((k) => (h.counts[k] ?? 0) > 0)
                        .map((k) => (
                          <span
                            key={k}
                            className="mr-3"
                            style={{
                              color:
                                k === 'PASS'
                                  ? 'var(--ok)'
                                  : k === 'FAIL' || k === 'ERROR'
                                    ? 'var(--accent)'
                                    : 'var(--muted)',
                            }}
                          >
                            {k} {h.counts[k]}
                          </span>
                        ))}
                    </td>
                    <td className="px-2 py-2 text-muted">{(h.elapsed_ms / 1000).toFixed(0)}s</td>
                    <td className="px-4 py-2 text-right">
                      {h.has_report && (
                        <>
                          <button
                            onClick={() => setRunId(h.run_id)}
                            className="mr-3 text-ink underline-offset-4 hover:underline"
                          >
                            {t('view')}
                          </button>
                          <a
                            href={reportDownloadUrl(h.run_id)}
                            className="text-ink underline-offset-4 hover:underline"
                          >
                            {t('download')}
                          </a>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </section>
      )}

      <section className="mt-8">
        <button
          onClick={() => setEditorOpen((o) => !o)}
          className="font-mono text-sm text-ink-soft underline-offset-4 hover:underline"
        >
          {editorOpen ? '▾' : '▸'} {t('editorTitle')}
        </button>
        <AnimatePresence>
          {editorOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <Card className="mt-3">
                <textarea
                  className={`${inputCls} min-h-[220px]`}
                  value={caseYaml}
                  onChange={(e) => setCaseYaml(e.target.value)}
                  placeholder={t('editorPh')}
                />
                <div className="mt-3 flex items-center gap-4">
                  <button
                    onClick={onSaveCase}
                    className="rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
                  >
                    {t('editorSave')}
                  </button>
                  {caseStatus && <span className="font-mono text-sm text-fg">{caseStatus}</span>}
                </div>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </section>
    </div>
  )
}
