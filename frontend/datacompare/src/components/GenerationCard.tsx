import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  compareEnvironments,
  generateDiffSql,
  generateSyncConfig,
  syncConfigDownloadUrl,
  traceLineage,
  type CompareOptions,
} from '@/api'
import { Collapsible, inputCls, labelCls, smallBtnCls } from '@/components/Collapsible'

// Generation features (legacy ui.py accordions C / 5C / AA): SeaTunnel
// sync-config generation with a real-password download, diff-SQL from
// the last keyed diff, lineage from SQL, and multi-environment compare.
export function GenerationCard({
  sessionId,
  tableA,
  tableB,
  options,
  onResult,
}: {
  sessionId: string
  tableA: string
  tableB: string
  options: CompareOptions
  onResult: (html: string) => void
}) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language.startsWith('zh') ? 'zh' : 'en'
  const [busy, setBusy] = useState(false)
  const [downloadId, setDownloadId] = useState('')
  const [lineageSql, setLineageSql] = useState('')
  const [envA, setEnvA] = useState('')
  const [envB, setEnvB] = useState('')
  const [envTable, setEnvTable] = useState('')

  const guard = async (fn: () => Promise<void>) => {
    setBusy(true)
    try {
      await fn()
    } catch (e) {
      onResult(
        `<div style="color:var(--accent);font-family:monospace;font-size:13px;">❌ ${
          e instanceof Error ? e.message : String(e)
        }</div>`,
      )
    } finally {
      setBusy(false)
    }
  }

  const onGenSync = () =>
    guard(async () => {
      const r = await generateSyncConfig({
        session_id: sessionId,
        table_a: tableA,
        table_b: tableB,
        column_mapping: options.column_mapping,
        lang,
      })
      setDownloadId(r.download_id ?? '')
      onResult(r.html)
    })

  const onGenDiffSql = () =>
    guard(async () => {
      onResult(
        await generateDiffSql({
          session_id: sessionId,
          table_a: tableA,
          table_b: tableB,
          lang,
        }),
      )
    })

  const onLineage = () =>
    guard(async () => {
      onResult(await traceLineage({ table: tableA, sqls: lineageSql, lang }))
    })

  const onCompareEnvs = () =>
    guard(async () => {
      onResult(
        await compareEnvironments({
          env_a: envA,
          env_b: envB,
          table: envTable,
          where: options.where,
          lang,
        }),
      )
    })

  return (
    <>
      <Collapsible title={t('genSync')} testId="sync-card">
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className={smallBtnCls} disabled={busy} onClick={onGenSync}>
            {t('genSync')}
          </button>
          {downloadId && (
            <a
              href={syncConfigDownloadUrl(downloadId)}
              download="seatunnel_sync.conf"
              data-testid="sync-download"
              className={smallBtnCls}
            >
              {t('genSyncDownload')}
            </a>
          )}
          <button type="button" className={smallBtnCls} disabled={busy} onClick={onGenDiffSql}>
            {t('genDiffSql')}
          </button>
        </div>
      </Collapsible>

      <Collapsible title={t('lineageTitle')} testId="lineage-card">
        <label className={labelCls} htmlFor="lineage-sql">
          {t('lineageHint')}
        </label>
        <textarea
          id="lineage-sql"
          className={`${inputCls} min-h-[72px]`}
          placeholder="SELECT * FROM source_table ..."
          value={lineageSql}
          onChange={(e) => setLineageSql(e.target.value)}
        />
        <button
          type="button"
          className={`${smallBtnCls} mt-2`}
          disabled={busy}
          onClick={onLineage}
        >
          {t('lineageTitle')}
        </button>
      </Collapsible>

      <Collapsible title={t('envTitle')} testId="env-card">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls} htmlFor="env-a">
              {t('envA')}
            </label>
            <input
              id="env-a"
              className={inputCls}
              placeholder={t('envHint')}
              value={envA}
              onChange={(e) => setEnvA(e.target.value)}
            />
          </div>
          <div>
            <label className={labelCls} htmlFor="env-b">
              {t('envB')}
            </label>
            <input
              id="env-b"
              className={inputCls}
              placeholder={t('envHint')}
              value={envB}
              onChange={(e) => setEnvB(e.target.value)}
            />
          </div>
        </div>
        <div className="mt-3">
          <label className={labelCls} htmlFor="env-table">
            {t('selectTable')}
          </label>
          <input
            id="env-table"
            className={inputCls}
            placeholder="orders"
            value={envTable}
            onChange={(e) => setEnvTable(e.target.value)}
          />
        </div>
        <button
          type="button"
          className={`${smallBtnCls} mt-3`}
          disabled={busy}
          onClick={onCompareEnvs}
        >
          {t('compareEnvs')}
        </button>
      </Collapsible>
    </>
  )
}
