import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import {
  fetchMetricHealth,
  fetchWeeklyReport,
  type HealthRow,
  type SessionMeta,
} from '@/api'

const DOT: Record<string, string> = {
  red: 'var(--accent)',
  yellow: 'var(--warn, #b8860b)',
  green: 'var(--ok)',
}

export function HealthView({ session }: { session: SessionMeta | null }) {
  const { t } = useTranslation()
  const [rows, setRows] = useState<HealthRow[]>([])
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(() => {
    if (!session) return
    setLoading(true)
    setErr('')
    fetchMetricHealth(session.session_id)
      .then((r) => setRows(r.rows))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [session])
  useEffect(refresh, [refresh])

  if (!session) {
    return (
      <Card>
        <div className="py-4 text-center font-mono text-[13px] text-muted">
          {t('healthNeedsSession')}
        </div>
      </Card>
    )
  }

  return (
    <div className="st-health-view space-y-4">
      <Card>
        <div className="mb-2 flex items-center gap-3 font-mono text-[12px]">
          <span className="uppercase tracking-[0.18em] text-ink-soft">
            {t('healthTitle')}
          </span>
          <button onClick={refresh} className="rounded border border-line px-2 text-muted">
            {loading ? '…' : '⟳'}
          </button>
          <button
            onClick={async () => {
              if (!session) return
              try {
                const r = await fetchWeeklyReport(session.session_id)
                const blob = new Blob([r.markdown], { type: 'text/markdown' })
                const a = document.createElement('a')
                a.href = URL.createObjectURL(blob)
                a.download = `weekly_${r.week.end.split('-').join('')}.md`
                a.click()
                URL.revokeObjectURL(a.href)
              } catch (e) {
                setErr(e instanceof Error ? e.message : String(e))
              }
            }}
            className="ml-auto rounded border border-ink px-3 text-ink hover:bg-ink hover:text-paper"
          >
            📄 {t('weeklyReport')}
          </button>
        </div>
        <table className="w-full font-mono text-[13px]">
          <thead>
            <tr className="border-b-2 border-ink text-left">
              <th className="px-2 py-1 text-ink" />
              <th className="px-2 py-1 text-ink">{t('healthMetric')}</th>
              <th className="px-2 py-1 text-ink">{t('healthFreshness')}</th>
              <th className="px-2 py-1 text-ink">{t('health7d')}</th>
              <th className="px-2 py-1 text-ink">{t('healthTarget')}</th>
              <th className="px-2 py-1 text-ink">{t('healthSubs')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.metric} className="border-b border-line last:border-b-0">
                <td className="px-2 py-1" style={{ color: DOT[r.status] }}>
                  ●
                </td>
                <td className="px-2 py-1 text-fg">
                  {r.metric}
                  <span className="text-muted">（{r.display_name}）</span>
                  {r.alerting && (
                    <span style={{ color: 'var(--accent)' }}>
                      {' '}
                      ⚠ {r.alerting_since}
                    </span>
                  )}
                </td>
                <td className="px-2 py-1 text-muted">
                  {r.freshness_error
                    ? t('healthCheckFailed')
                    : r.latest_day
                      ? `${r.latest_day}${r.lag_days ? ` (+${r.lag_days}d)` : ''}`
                      : '—'}
                </td>
                <td className="px-2 py-1 text-muted">
                  {r.queries_7d}/{r.failures_7d}/{r.alerts_7d}
                </td>
                <td className="px-2 py-1 text-muted">
                  {r.month_completion_pct != null
                    ? `${r.month_completion_pct}%`
                    : r.target_error
                      ? t('healthCheckFailed')
                      : '—'}
                </td>
                <td className="px-2 py-1 text-muted">{r.subscriptions || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !loading && (
          <div className="py-4 text-center font-mono text-[13px] text-muted">—</div>
        )}
        {err && <div className="mt-2 font-mono text-[12px] text-accent">{err}</div>}
      </Card>
    </div>
  )
}
