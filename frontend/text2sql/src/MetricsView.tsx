import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { fetchMetrics, type MetricInfo } from '@/api'

/** The #metrics view: browse the metrics catalog, expand details, use in chat. */
export function MetricsView({ onUse }: { onUse: (text: string) => void }) {
  const { t, i18n } = useTranslation()
  const [metrics, setMetrics] = useState<MetricInfo[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetchMetrics().then((r) => setMetrics(r.metrics))
  }, [])

  const filtered = search
    ? metrics.filter(
        (m) =>
          m.name.toLowerCase().includes(search.toLowerCase()) ||
          m.display_name.toLowerCase().includes(search.toLowerCase()) ||
          m.description.toLowerCase().includes(search.toLowerCase()),
      )
    : metrics

  const applyMetric = (m: MetricInfo) => {
    const dim = m.dimensions[0]
    const name = m.display_name || m.name
    const text = dim
      ? i18n.language === 'zh'
        ? `查看 ${name} 按 ${dim} 分布`
        : `Show ${name} broken down by ${dim}`
      : i18n.language === 'zh'
        ? `查看 ${name}`
        : `Show ${name}`
    onUse(text)
  }

  return (
    <div className="st-metrics-view space-y-4">
      <Card>
        <div className="mb-2 flex items-center gap-3 font-mono text-[12px]">
          <span className="uppercase tracking-[0.18em] text-ink-soft">{t('metricsCatalog')}</span>
          <span className="text-muted">{filtered.length}</span>
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('searchMetrics')}
          className="mb-3 w-full rounded border border-line bg-paper px-2 py-1 font-mono text-[13px] text-fg outline-none focus:border-ink"
        />
        <table className="w-full font-mono text-[13px]">
          <thead>
            <tr className="border-b-2 border-ink text-left">
              <th className="px-2 py-1 text-ink">{t('metricName')}</th>
              <th className="px-2 py-1 text-ink">{t('description')}</th>
              <th className="px-2 py-1 text-ink">{t('metricType')}</th>
              <th className="px-2 py-1 text-ink">{t('tables')}</th>
              <th className="px-2 py-1 text-ink" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((m) => (
              <>
                <tr
                  key={m.name}
                  onClick={() => setExpanded(expanded === m.name ? null : m.name)}
                  className={
                    'cursor-pointer border-b border-line last:border-b-0 ' +
                    (expanded === m.name ? 'bg-paper' : '')
                  }
                >
                  <td className="px-2 py-1 text-fg">{m.display_name || m.name}</td>
                  <td className="max-w-[240px] truncate px-2 py-1 text-muted">{m.description}</td>
                  <td className="px-2 py-1 text-muted">{m.type}</td>
                  <td className="px-2 py-1 text-muted">{m.table}</td>
                  <td className="px-2 py-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        applyMetric(m)
                      }}
                      className="rounded border border-ink px-2 text-ink hover:bg-ink hover:text-paper"
                    >
                      {t('useMetric')}
                    </button>
                  </td>
                </tr>
                {expanded === m.name && (
                  <tr key={m.name + '-detail'}>
                    <td colSpan={5} className="border-b border-line bg-paper px-3 py-2">
                      <div className="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-[12px]">
                        {m.expression && (
                          <>
                            <span className="text-ink-soft">{t('expression')}</span>
                            <span className="text-fg">{m.expression}</span>
                          </>
                        )}
                        {m.numerator && (
                          <>
                            <span className="text-ink-soft">{t('formula')}</span>
                            <span className="text-fg">
                              {m.numerator} / {m.denominator}
                            </span>
                          </>
                        )}
                        {m.dimensions.length > 0 && (
                          <>
                            <span className="text-ink-soft">{t('dimensions')}</span>
                            <span className="text-fg">{m.dimensions.join(', ')}</span>
                          </>
                        )}
                        {m.unit && (
                          <>
                            <span className="text-ink-soft">{t('unit')}</span>
                            <span className="text-fg">{m.unit}</span>
                          </>
                        )}
                        {m.owner && (
                          <>
                            <span className="text-ink-soft">{t('owner')}</span>
                            <span className="text-fg">{m.owner}</span>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="py-4 text-center font-mono text-[13px] text-muted">—</div>
        )}
      </Card>
    </div>
  )
}
