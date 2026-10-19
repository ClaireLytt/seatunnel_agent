import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { historyRecent, type HistoryRecord } from '@/api'

import { fieldCls, labelCls, smallBtnCls as btnCls } from '@/ui'

function verdictMark(rec: HistoryRecord): string {
  const c = rec.counts ?? {}
  return `⛔${c.high ?? 0} ⚠️${c.medium ?? 0} 🔵${c.low ?? 0}`
}

function snippet(rec: HistoryRecord, n: number): string {
  return (rec.sql ?? '').split(/\s+/).join(' ').slice(0, n)
}

export function HistoryPanel({
  onLoad,
}: {
  onLoad: (sql: string, dialect: string) => void
}) {
  const { t } = useTranslation()
  const [records, setRecords] = useState<HistoryRecord[]>([])
  const [picked, setPicked] = useState<number>(0)
  const [empty, setEmpty] = useState(false)

  const refresh = async () => {
    try {
      const recs = await historyRecent()
      setRecords(recs)
      setPicked(0)
      setEmpty(recs.length === 0)
    } catch {
      setRecords([])
      setEmpty(true)
    }
  }

  const load = () => {
    const rec = records[picked]
    if (rec) onLoad(rec.sql ?? '', rec.dialect ?? 'spark')
  }

  return (
    <Card>
      <details>
        <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
          {t('history_accordion')}
        </summary>
        <div className="mt-3 flex flex-col gap-3">
          <div>
            <label className={labelCls}>{t('history_pick')}</label>
            <select
              value={picked}
              onChange={(e) => setPicked(Number(e.target.value))}
              className={fieldCls}
            >
              {records.map((r, i) => (
                <option key={i} value={i}>
                  {`${String(r.timestamp ?? '').slice(5, 16)} · ${r.dialect ?? ''} · ${verdictMark(r)} · ${snippet(r, 40)}`}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <button onClick={refresh} className={btnCls}>
              {t('history_refresh')}
            </button>
            <button onClick={load} disabled={!records.length} className={btnCls}>
              {t('history_load')}
            </button>
          </div>
          {empty && <p className="text-sm italic text-muted">{t('history_empty')}</p>}
          {records.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr>
                    {(['h_time', 'h_source', 'h_dialect', 'h_mode', 'h_findings', 'h_sql'] as const).map(
                      (k) => (
                        <th
                          key={k}
                          className="border border-line px-2 py-1 text-left font-mono text-[11px] uppercase tracking-wider text-ink-soft"
                        >
                          {t(k)}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {records.map((r, i) => (
                    <tr key={i}>
                      <td className="border border-line px-2 py-1">
                        {String(r.timestamp ?? '').slice(0, 16)}
                      </td>
                      <td className="border border-line px-2 py-1">{r.source ?? ''}</td>
                      <td className="border border-line px-2 py-1">{r.dialect ?? ''}</td>
                      <td className="border border-line px-2 py-1">{r.mode ?? ''}</td>
                      <td className="border border-line px-2 py-1 whitespace-nowrap">
                        {verdictMark(r)}
                      </td>
                      <td className="border border-line px-2 py-1 font-mono">
                        {snippet(r, 60)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </details>
    </Card>
  )
}
