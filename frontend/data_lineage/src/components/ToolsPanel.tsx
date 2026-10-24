import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { langOf } from '@shared/lang'
import {
  ApiError,
  findPath,
  healthCheck,
  listSnapshots,
  saveSnapshot,
  search,
  slaImpact,
  snapshotDiff,
  type SnapshotInfo,
  type SourceParams,
} from '@/api'
import { fieldCls, labelCls, smallBtnCls } from '@/ui'

/** Search + advanced analysis + snapshots (legacy side-panel sections). */
export function ToolsPanel({
  src,
  table,
  depth,
  tables,
  onResult,
  onNotice,
}: {
  src: () => SourceParams
  table: string
  depth: number
  tables: string[]
  onResult: (report: string, mermaid?: string) => void
  onNotice: (notice: string) => void
}) {
  const { t, i18n } = useTranslation()
  const [keyword, setKeyword] = useState('')
  const [searchMd, setSearchMd] = useState('')
  const [pathDst, setPathDst] = useState('')
  const [slaDelay, setSlaDelay] = useState(1)
  const [snapName, setSnapName] = useState('')
  const [snaps, setSnaps] = useState<SnapshotInfo[]>([])
  const [snapPick, setSnapPick] = useState('')
  const [snapMd, setSnapMd] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    listSnapshots().then((r) => setSnaps(r.snapshots)).catch(() => {})
  }, [])

  const guard = async (fn: () => Promise<void>) => {
    setBusy(true)
    onNotice('')
    try {
      await fn()
    } catch (e) {
      if (e instanceof ApiError && e.code === 'need_graph') onNotice(t('need_graph'))
      else if (e instanceof ApiError && e.suggestions.length) {
        onNotice(e.message + '\n' + e.suggestions.map((s) => `- ${s}`).join('\n'))
      } else onNotice(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const doSearch = () => {
    if (!keyword.trim()) {
      setSearchMd(t('need_keyword'))
      return
    }
    void guard(async () => {
      const res = await search(src(), keyword.trim())
      setSearchMd(res.matches.length
        ? res.matches.map((m) => (m.layer ? `• ${m.name}（${m.layer}）` : `• ${m.name}`)).join('\n')
        : t('no_match', { kw: keyword.trim() }))
    })
  }

  const doPath = () => {
    if (!table.trim()) return onNotice(t('need_table'))
    if (!pathDst.trim()) return onNotice(t('need_path_dst'))
    void guard(async () => {
      const res = await findPath(src(), table.trim(), pathDst.trim())
      onResult(res.markdown, res.mermaid)
    })
  }

  const doSla = () => {
    if (!table.trim()) return onNotice(t('need_table'))
    void guard(async () => {
      const res = await slaImpact(src(), table.trim(), slaDelay, depth)
      onResult(res.markdown, res.mermaid)
    })
  }

  const doHealth = () =>
    void guard(async () => {
      const res = await healthCheck(src(), langOf(i18n))
      onResult(res.markdown)
    })

  const doSaveSnap = () =>
    void guard(async () => {
      const res = await saveSnapshot(src(), snapName.trim())
      setSnapMd(t('snap_saved', { file: res.file }))
      const list = await listSnapshots()
      setSnaps(list.snapshots)
      setSnapPick(res.file)  // legacy auto-selected the fresh snapshot
    })

  const doDiffSnap = () => {
    if (!snapPick) {
      setSnapMd(t('need_snap'))
      return
    }
    void guard(async () => {
      const res = await snapshotDiff(src(), snapPick)
      onResult(res.markdown)
    })
  }

  return (
    <>
      <Card>
        <label className={labelCls}>{t('search_label')}</label>
        <div className="flex gap-2">
          <input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder={t('search_ph')}
            spellCheck={false}
            className={fieldCls}
          />
          <button onClick={doSearch} disabled={busy} className={smallBtnCls}>
            {t('search_btn')}
          </button>
        </div>
        {searchMd && (
          <pre className="mt-2 whitespace-pre-wrap font-mono text-[12px] text-muted">{searchMd}</pre>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 font-display text-base font-bold text-ink">{t('adv_heading')}</h2>
        <label className={labelCls} title={t('path_dst_info')}>{t('path_dst_label')}</label>
        <div className="flex gap-2">
          <input
            list="lin-tables-dst"
            value={pathDst}
            onChange={(e) => setPathDst(e.target.value)}
            spellCheck={false}
            className={fieldCls}
          />
          <datalist id="lin-tables-dst">
            {tables.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          <button onClick={doPath} disabled={busy} className={smallBtnCls}>
            {t('path_btn')}
          </button>
        </div>
        <label className={`${labelCls} mt-3`}>{t('sla_delay_label')}</label>
        <div className="flex gap-2">
          <input
            type="number"
            min={0}
            value={slaDelay}
            onChange={(e) => setSlaDelay(Math.max(0, Number(e.target.value)))}
            className={fieldCls}
          />
          <button onClick={doSla} disabled={busy} className={`${smallBtnCls} whitespace-nowrap`}>
            {t('sla_btn')}
          </button>
        </div>
        <button onClick={doHealth} disabled={busy} className={`${smallBtnCls} mt-3 w-full`}>
          {t('health_btn')}
        </button>
      </Card>

      <Card>
        <h2 className="mb-3 font-display text-base font-bold text-ink">{t('snap_heading')}</h2>
        <label className={labelCls}>{t('snap_name_label')}</label>
        <div className="flex gap-2">
          <input
            value={snapName}
            onChange={(e) => setSnapName(e.target.value)}
            spellCheck={false}
            className={fieldCls}
          />
          <button onClick={doSaveSnap} disabled={busy} className={`${smallBtnCls} whitespace-nowrap`}>
            {t('save_snap_btn')}
          </button>
        </div>
        <label className={`${labelCls} mt-3`}>{t('snap_dd_label')}</label>
        <div className="flex gap-2">
          <select value={snapPick} onChange={(e) => setSnapPick(e.target.value)} className={fieldCls}>
            <option value=""></option>
            {snaps.map((s) => (
              <option key={s.file} value={s.file}>
                {`${s.name || s.file}（${s.saved_at ?? ''}）`}
              </option>
            ))}
          </select>
          <button onClick={doDiffSnap} disabled={busy} className={`${smallBtnCls} whitespace-nowrap`}>
            {t('diff_snap_btn')}
          </button>
        </div>
        {snapMd && <p className="mt-2 text-sm text-muted">{snapMd}</p>}
      </Card>
    </>
  )
}
