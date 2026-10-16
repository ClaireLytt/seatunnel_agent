import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { fetchSchema, fetchTable, type SessionMeta, type TableDetail, type TableInfo } from '@/api'

/** The #schema view: table list + column detail card. */
export function SchemaBrowser({ session }: { session: SessionMeta }) {
  const { t } = useTranslation()
  const [tables, setTables] = useState<TableInfo[]>([])
  const [detail, setDetail] = useState<TableDetail | null>(null)

  useEffect(() => {
    fetchSchema(session.session_id)
      .then((r) => setTables(r.tables))
      .catch(console.error)
  }, [session])

  return (
    <div className="st-schema-browser grid grid-cols-[280px_1fr] gap-4">
      <Card className="max-h-[70vh] overflow-y-auto p-3">
        <div className="mb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
          {t('tables')} ({tables.length})
        </div>
        {tables.map((tb) => (
          <button
            key={tb.name}
            onClick={() => fetchTable(session.session_id, tb.name).then(setDetail)}
            className={
              'block w-full rounded px-2 py-1 text-left font-mono text-[13px] ' +
              (detail?.name === tb.name ? 'bg-ink text-paper' : 'text-fg hover:bg-paper')
            }
          >
            {tb.name}
            <span className="float-right text-muted">{tb.column_count}</span>
          </button>
        ))}
      </Card>
      <Card className="max-h-[70vh] overflow-y-auto">
        {detail ? (
          <div className="st-table-detail">
            <h3 className="font-display text-lg font-bold text-ink">{detail.name}</h3>
            {detail.comment && <p className="mb-2 text-sm text-muted">{detail.comment}</p>}
            <table className="w-full font-mono text-[13px]">
              <thead>
                <tr className="border-b-2 border-ink text-left">
                  <th className="px-2 py-1 text-ink">{t('column')}</th>
                  <th className="px-2 py-1 text-ink">{t('colType')}</th>
                  <th className="px-2 py-1 text-ink">{t('comment')}</th>
                </tr>
              </thead>
              <tbody>
                {detail.columns.map((c) => (
                  <tr key={c.name} className="border-b border-line last:border-b-0">
                    <td className="px-2 py-1 text-fg">{c.name}</td>
                    <td className="px-2 py-1 text-muted">{c.type}</td>
                    <td className="px-2 py-1 text-muted">{c.comment}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {detail.partition_columns.length > 0 && (
              <div className="mt-2 font-mono text-[12px] text-muted">
                {t('partitions')}: {detail.partition_columns.map((c) => c.name).join(', ')}
              </div>
            )}
          </div>
        ) : (
          <div className="font-mono text-sm text-muted">—</div>
        )}
      </Card>
    </div>
  )
}
