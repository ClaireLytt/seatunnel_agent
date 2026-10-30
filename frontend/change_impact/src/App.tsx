import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { analyzeImpact, ApiError } from '@/api'
import { GraphView } from '@/components/GraphView'
import { ReportView } from '@shared/components/ReportView'
import { fieldCls, labelCls } from '@/ui'

// SQL_DIALECTS from sqlglot_lineage (impact shares the lineage parser).
const SQL_DIALECTS = [
  'hive',
  'spark',
  'flink',
  'maxcompute',
  'mysql',
  'postgresql',
  'clickhouse',
  'doris',
  'starrocks',
  'sqlite',
]

type Mode = 'dirs' | 'paste'

export default function App() {
  const { t, i18n } = useTranslation()
  const [mode, setMode] = useState<Mode>('dirs')
  const [oldDir, setOldDir] = useState('')
  const [newDir, setNewDir] = useState('')
  const [oldSql, setOldSql] = useState('')
  const [newSql, setNewSql] = useState('')
  const [ctxDir, setCtxDir] = useState('')
  const [dialect, setDialect] = useState('hive')
  const [depth, setDepth] = useState(3)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [report, setReport] = useState('')
  const [mermaidSrc, setMermaidSrc] = useState('')

  const run = async () => {
    setNotice('')
    if (mode === 'dirs') {
      if (!oldDir.trim() || !newDir.trim()) {
        setReport('')
        setMermaidSrc('')
        setNotice(t('need_dirs'))
        return
      }
    } else if (!oldSql.trim() || !newSql.trim()) {
      setReport('')
      setMermaidSrc('')
      setNotice(t('need_sql'))
      return
    }
    setBusy(true)
    try {
      const res = await analyzeImpact({
        ...(mode === 'dirs'
          ? { old_dir: oldDir.trim(), new_dir: newDir.trim() }
          : {
              old_sql: oldSql,
              new_sql: newSql,
              ...(ctxDir.trim() ? { context_dir: ctxDir.trim() } : {}),
            }),
        depth,
        sql_dialect: dialect,
        lang: i18n.language,
      })
      // paste mode appends the unified SQL diff (legacy do_analyze_sql)
      setReport(res.sql_diff ? `${res.report}\n\n${res.sql_diff}` : res.report)
      setMermaidSrc(res.mermaid ?? '')
    } catch (e) {
      setReport('')
      setMermaidSrc('')
      if (e instanceof ApiError && e.code === 'bad_dir') {
        setNotice(t('bad_dir', { d: e.path }))
      } else if (e instanceof ApiError && e.code === 'analyze_failed') {
        // raw exception text inside the localized fail template (legacy)
        setNotice(t('fail', { exc: e.error }))
      } else {
        setNotice(t('fail', { exc: e instanceof Error ? e.message : String(e) }))
      }
    } finally {
      setBusy(false)
    }
  }

  const tabCls = (active: boolean) =>
    `rounded-t border-[1.5px] border-b-0 px-4 py-1.5 font-mono text-xs font-semibold transition ${
      active
        ? 'border-ink bg-ink text-[var(--paper)]'
        : 'border-line text-ink-soft hover:border-ink'
    }`

  return (
    <div className="mx-auto max-w-[1360px] px-4 py-8">
      <PageHeader badge="data / impact" titlePrefix="💥" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <div className="mb-3 flex gap-1">
              <button className={tabCls(mode === 'dirs')} onClick={() => setMode('dirs')}>
                {t('tab_dirs')}
              </button>
              <button className={tabCls(mode === 'paste')} onClick={() => setMode('paste')}>
                {t('tab_paste')}
              </button>
            </div>

            {mode === 'dirs' ? (
              <div className="flex flex-col gap-3">
                <div>
                  <label className={labelCls}>{t('old_label')}</label>
                  <input
                    value={oldDir}
                    onChange={(e) => setOldDir(e.target.value)}
                    placeholder={t('old_ph')}
                    spellCheck={false}
                    className={fieldCls}
                  />
                </div>
                <div>
                  <label className={labelCls}>{t('new_label')}</label>
                  <input
                    value={newDir}
                    onChange={(e) => setNewDir(e.target.value)}
                    placeholder={t('new_ph')}
                    spellCheck={false}
                    className={fieldCls}
                  />
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <div>
                  <label className={labelCls}>{t('old_sql_label')}</label>
                  <textarea
                    value={oldSql}
                    onChange={(e) => setOldSql(e.target.value)}
                    placeholder={t('old_sql_ph')}
                    rows={8}
                    spellCheck={false}
                    className={`${fieldCls} resize-y`}
                  />
                </div>
                <div>
                  <label className={labelCls}>{t('new_sql_label')}</label>
                  <textarea
                    value={newSql}
                    onChange={(e) => setNewSql(e.target.value)}
                    placeholder={t('new_sql_ph')}
                    rows={8}
                    spellCheck={false}
                    className={`${fieldCls} resize-y`}
                  />
                </div>
                <div>
                  <label className={labelCls}>{t('ctx_label')}</label>
                  <input
                    value={ctxDir}
                    onChange={(e) => setCtxDir(e.target.value)}
                    placeholder={t('ctx_ph')}
                    spellCheck={false}
                    className={fieldCls}
                  />
                </div>
              </div>
            )}

            <label className={`${labelCls} mt-3`}>{t('dialect_label')}</label>
            <select
              value={dialect}
              onChange={(e) => setDialect(e.target.value)}
              className={fieldCls}
            >
              {SQL_DIALECTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <label className={`${labelCls} mt-3`}>
              {t('depth_label')}: <span className="normal-case">{depth}</span>
            </label>
            <input
              type="range"
              min={1}
              max={10}
              step={1}
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              className="w-full accent-[var(--ink)]"
            />
            <button
              onClick={run}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {busy ? t('running') : mode === 'dirs' ? t('analyze_btn') : t('analyze_sql_btn')}
            </button>
          </Card>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col gap-4">
          <Card>
            {notice && (
              <div className="mb-3 text-sm" style={{ color: 'var(--accent)' }}>
                {/* legacy wrote guards into gr.Markdown — keep markdown */}
                <ReportView className="imp-report" markdown={notice} />
              </div>
            )}
            {mermaidSrc && <GraphView source={mermaidSrc} />}
            {report ? (
              <div className="mt-4">
                <ReportView className="imp-report" markdown={report} />
              </div>
            ) : (
              !notice && <p className="text-sm italic text-muted">{t('result_ph')}</p>
            )}
          </Card>
        </main>
      </div>
    </div>
  )
}
