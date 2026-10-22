import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import {
  ApiError,
  build,
  getSessionId,
  query,
  type SourceParams,
} from '@/api'
import { AgentPanel } from '@/components/AgentPanel'
import { GraphView } from '@/components/GraphView'
import { ReportView } from '@shared/components/ReportView'
import { ToolsPanel } from '@/components/ToolsPanel'
import { fieldCls, labelCls, smallBtnCls } from '@/ui'

const SQL_DIALECTS = ['hive', 'spark', 'mysql', 'postgresql', 'clickhouse', 'doris', 'starrocks']

export default function App() {
  const { t } = useTranslation()
  const [sessionId, setSessionId] = useState('')
  // data sources
  const [sqlDir, setSqlDir] = useState('')
  const [sqlDialect, setSqlDialect] = useState('hive')
  const [stDir, setStDir] = useState('')
  const [useHive, setUseHive] = useState(false)
  const [metaTable, setMetaTable] = useState('')
  const [partition, setPartition] = useState('')
  const [stats, setStats] = useState('')
  const [tables, setTables] = useState<string[]>([])
  // query
  const [table, setTable] = useState('')
  const [direction, setDirection] = useState('both')
  const [depth, setDepth] = useState(3)
  const [column, setColumn] = useState('')
  // results
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [report, setReport] = useState('')
  const [mermaidSrc, setMermaidSrc] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    getSessionId().then(setSessionId).catch(() => {})
  }, [])

  const src = useCallback((): SourceParams => ({
    session_id: sessionId,
    sql_dir: sqlDir.trim() || undefined,
    sql_dialect: sqlDialect,
    seatunnel_dir: stDir.trim() || undefined,
    use_hive: useHive,
    meta_table: metaTable.trim() || undefined,
    partition: partition.trim() || undefined,
  }), [sessionId, sqlDir, sqlDialect, stDir, useHive, metaTable, partition])

  const showError = (e: unknown) => {
    if (e instanceof ApiError) {
      if (e.code === 'need_graph') {
        setNotice(t('need_graph'))
      } else if (e.code === 'not_found') {
        // localized not_found + similar-table list (legacy _not_found_md)
        const missing = /'([^']+)'/.exec(e.message)?.[1] ?? ''
        let msg = t('not_found', { table: missing })
        if (e.suggestions.length) {
          msg += `\n${t('similar')}\n` + e.suggestions.map((s) => `- ${s}`).join('\n')
        }
        setNotice(msg)
      } else {
        let msg = e.message
        if (e.suggestions.length) {
          msg += '\n' + e.suggestions.map((s) => `- ${s}`).join('\n')
        }
        setNotice(msg)
      }
    } else {
      setNotice(String(e))
    }
  }

  const doBuild = async () => {
    if (!sqlDir.trim() && !stDir.trim() && !useHive) {
      setStats(t('need_source'))
      return
    }
    setBusy(true)
    try {
      const res = await build(src())
      const s = res.stats
      setStats([
        t('built_stats', {
          tables: s.tables, edges: s.edges,
          col_edges: s.column_edges, sla: s.sla_tables,
        }),
        ...res.warnings.map((w) => `⚠️ ${w}`),
      ].join('\n'))
      setTables(res.tables)
    } catch (e) {
      showError(e)
      setStats('')
    } finally {
      setBusy(false)
    }
  }

  const runQuery = useCallback(async (target?: string, noColumn = false) => {
    const tbl = (target ?? table).trim()
    setNotice('')
    if (!tbl) {
      setNotice(t('need_table'))
      return
    }
    setBusy(true)
    try {
      const res = await query(src(), tbl, direction, depth,
        noColumn ? '' : column.trim())
      setReport(res.report)
      setMermaidSrc(res.mermaid)
    } catch (e) {
      showError(e)
    } finally {
      setBusy(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [table, direction, depth, column, src, t])

  const onNodeClick = useCallback((name: string) => {
    setTable(name)
    // legacy do_node_jump queried with column=None
    void runQuery(name, true)
  }, [runQuery])

  const copySrc = async () => {
    try {
      await navigator.clipboard.writeText(mermaidSrc)
    } catch {
      /* http origin — ignore */
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-8">
      <PageHeader badge="data / lineage" titlePrefix="🩸" />

      <div className="st-lin-layout mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="st-lin-side flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <h2 className="mb-3 font-display text-base font-bold text-ink">{t('ds_heading')}</h2>
            <label className={labelCls}>{t('sql_dir_label')}</label>
            <input
              value={sqlDir}
              onChange={(e) => setSqlDir(e.target.value)}
              placeholder={t('sql_dir_ph')}
              spellCheck={false}
              className={fieldCls}
            />
            <label className={`${labelCls} mt-3`} title={t('sql_dialect_info')}>{t('sql_dialect_label')}</label>
            <select value={sqlDialect} onChange={(e) => setSqlDialect(e.target.value)} className={fieldCls}>
              {SQL_DIALECTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <label className={`${labelCls} mt-3`}>{t('st_dir_label')}</label>
            <input
              value={stDir}
              onChange={(e) => setStDir(e.target.value)}
              placeholder={t('st_dir_ph')}
              spellCheck={false}
              className={fieldCls}
            />
            <label className="mt-3 flex cursor-pointer items-start gap-2 text-[13px] text-ink">
              <input
                type="checkbox"
                checked={useHive}
                onChange={(e) => setUseHive(e.target.checked)}
                className="mt-0.5 accent-[var(--ink)]"
              />
              {t('use_hive')}
            </label>
            <details className="mt-3">
              <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                {t('hive_adv')}
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                <div>
                  <label className={labelCls}>{t('meta_table_label')}</label>
                  <input
                    value={metaTable}
                    onChange={(e) => setMetaTable(e.target.value)}
                    placeholder={t('meta_table_ph')}
                    className={fieldCls}
                  />
                </div>
                <div>
                  <label className={labelCls}>{t('partition_label')}</label>
                  <input
                    value={partition}
                    onChange={(e) => setPartition(e.target.value)}
                    placeholder={t('partition_ph')}
                    className={fieldCls}
                  />
                </div>
              </div>
            </details>
            <button
              onClick={doBuild}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {t('load_btn')}
            </button>
            <div className="mt-2 whitespace-pre-wrap text-sm text-muted">
              {stats || t('not_loaded')}
            </div>
          </Card>

          <Card>
            <h2 className="mb-3 font-display text-base font-bold text-ink">{t('query_heading')}</h2>
            <label className={labelCls}>{t('table_label')}</label>
            <input
              list="lin-tables"
              value={table}
              onChange={(e) => setTable(e.target.value)}
              placeholder={t('table_info')}
              spellCheck={false}
              className={fieldCls}
            />
            <datalist id="lin-tables">
              {tables.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
            <label className={`${labelCls} mt-3`}>{t('direction_label')}</label>
            <select value={direction} onChange={(e) => setDirection(e.target.value)} className={fieldCls}>
              <option value="both">{t('dir_both')}</option>
              <option value="upstream">{t('dir_up')}</option>
              <option value="downstream">{t('dir_down')}</option>
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
            <label className={`${labelCls} mt-3`}>{t('column_label')}</label>
            <input
              value={column}
              onChange={(e) => setColumn(e.target.value)}
              placeholder={t('column_ph')}
              spellCheck={false}
              className={fieldCls}
            />
            <button
              onClick={() => void runQuery()}
              disabled={busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {t('query_btn')}
            </button>
          </Card>

          <ToolsPanel
            src={src}
            table={table}
            depth={depth}
            tables={tables}
            onResult={(md, mermaid) => {
              setNotice('')
              setReport(md)
              // empty mermaid keeps the prior graph (legacy gr.update())
              if (mermaid) setMermaidSrc(mermaid)
            }}
            onNotice={setNotice}
          />
        </aside>

        <main className="st-lin-main flex min-w-0 flex-1 flex-col gap-4">
          <Card>
            {notice && (
              <div className="mb-3 whitespace-pre-wrap font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {notice}
              </div>
            )}
            {mermaidSrc && <GraphView source={mermaidSrc} onNode={onNodeClick} />}
            {report ? (
              <div className="mt-4">
                <ReportView className="lin-report" markdown={report} />
              </div>
            ) : (
              !notice && <p className="text-sm italic text-muted">{t('report_ph')}</p>
            )}
          </Card>
          <AgentPanel src={src} onGraph={setMermaidSrc} />
          {mermaidSrc && (
            <Card>
              <details>
                <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                  {t('mermaid_acc')}
                </summary>
                <div className="mt-3">
                  <button onClick={copySrc} className={smallBtnCls}>
                    {copied ? `✓ ${t('copied')}` : t('copy')}
                  </button>
                  <pre className="mt-2 overflow-x-auto rounded border border-line bg-[var(--paper)] p-3 font-mono text-[12px] leading-relaxed">
                    {mermaidSrc}
                  </pre>
                </div>
              </details>
            </Card>
          )}
        </main>
      </div>
    </div>
  )
}
