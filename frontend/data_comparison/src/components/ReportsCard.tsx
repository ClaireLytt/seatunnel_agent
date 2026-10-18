import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'
import { diffReports, listReports, loadReport, saveReport } from '@/api'
import { Collapsible, inputCls, labelCls, smallBtnCls } from '@/components/Collapsible'

const lang = () => (i18n.language.startsWith('zh') ? 'zh' : 'en')

// Report persistence (legacy ui.py _save_report/_list_reports/_load_report
// + report diff ui.py:1353): save the current comparison under a
// table-pair filename, reload a saved report into the results panel,
// and diff two saved reports.
export function ReportsCard({
  sessionId,
  tableA,
  tableB,
  onResult,
}: {
  sessionId: string
  tableA: string
  tableB: string
  onResult: (html: string) => void
}) {
  const { t } = useTranslation()
  const [files, setFiles] = useState<string[]>([])
  const [selected, setSelected] = useState('')
  const [oldSel, setOldSel] = useState('')
  const [newSel, setNewSel] = useState('')
  const [status, setStatus] = useState('')

  const fail = (e: unknown) => setStatus(`❌ ${e instanceof Error ? e.message : e}`)

  const refresh = async () => {
    try {
      setFiles(await listReports())
    } catch (e) {
      fail(e)
    }
  }

  const onSave = async () => {
    try {
      const r = await saveReport({
        session_id: sessionId,
        table_a: tableA,
        table_b: tableB,
        lang: lang(),
      })
      if (r.ok) {
        setStatus(`✅ ${t('reportSaved')} — ${r.filename}`)
        await refresh()
      } else {
        setStatus(`❌ ${r.error}`)
      }
    } catch (e) {
      fail(e)
    }
  }

  const onLoad = async (name: string) => {
    setSelected(name)
    if (!name) return
    try {
      onResult(await loadReport(name, sessionId, lang()))
    } catch (e) {
      fail(e)
    }
  }

  const onDiff = async () => {
    if (!oldSel || !newSel) {
      setStatus(t('reportNoReports'))
      return
    }
    try {
      onResult(await diffReports(oldSel, newSel, lang()))
      setStatus('')
    } catch (e) {
      fail(e)
    }
  }

  const options = () => (
    <>
      <option value=""></option>
      {files.map((f) => (
        <option key={f} value={f}>
          {f}
        </option>
      ))}
    </>
  )

  return (
    <Collapsible title={t('reports')} onOpen={refresh} testId="reports-card">
      <div className="flex gap-2">
        <button type="button" className={smallBtnCls} onClick={onSave}>
          {t('reportSave')}
        </button>
        <button type="button" className={smallBtnCls} onClick={refresh}>
          {t('reportRefresh')}
        </button>
      </div>

      <div className="mt-3">
        <label className={labelCls} htmlFor="report-load">
          {t('reportLoad')}
        </label>
        <select
          id="report-load"
          className={inputCls}
          value={selected}
          onChange={(e) => onLoad(e.target.value)}
        >
          {options()}
        </select>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls} htmlFor="report-old">
            {t('reportOld')}
          </label>
          <select
            id="report-old"
            className={inputCls}
            value={oldSel}
            onChange={(e) => setOldSel(e.target.value)}
          >
            {options()}
          </select>
        </div>
        <div>
          <label className={labelCls} htmlFor="report-new">
            {t('reportNew')}
          </label>
          <select
            id="report-new"
            className={inputCls}
            value={newSel}
            onChange={(e) => setNewSel(e.target.value)}
          >
            {options()}
          </select>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <button type="button" className={smallBtnCls} onClick={onDiff}>
          {t('reportDiff')}
        </button>
        {status && (
          <span
            data-testid="report-status"
            className="min-w-0 flex-1 truncate font-mono text-[12px]"
            style={{ color: status.startsWith('✅') ? 'var(--ok)' : 'var(--accent)' }}
            title={status}
          >
            {status}
          </span>
        )}
      </div>
    </Collapsible>
  )
}
