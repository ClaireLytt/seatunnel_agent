import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { AGENT_KEYS, fetchStats, type AgentStats, type StatsRecord } from '@/api'

const PAGES: Record<string, string> = {
  hygiene: '/hygiene',
  metaquality: '/metaquality',
  contract: '/contract',
  grants: '/grants',
  ddlguard: '/ddlguard',
}

function totals(records: StatsRecord[]): number[] {
  return records.map((r) => r.counts?.total ?? 0)
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null
  const w = 220
  const h = 36
  const max = Math.max(...values, 1)
  const pts = values
    .map((v, i) => `${(i * w) / (values.length - 1)},${h - 4 - (v / max) * (h - 8)}`)
    .join(' ')
  return (
    <svg width={w} height={h} className="mt-2 block" aria-hidden="true">
      <polyline
        points={pts}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        className="text-ink-soft"
      />
      {values.map((v, i) => (
        <circle
          key={i}
          cx={(i * w) / (values.length - 1)}
          cy={h - 4 - (v / max) * (h - 8)}
          r="2"
          className="fill-current text-ink"
        />
      ))}
    </svg>
  )
}

function AgentCard({ stats }: { stats: AgentStats }) {
  const { t } = useTranslation()
  const records = stats.records ?? []
  const latest = records.length ? records[records.length - 1] : null
  const series = totals(records)
  const c = latest?.counts ?? {}
  return (
    <Card>
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="font-semibold">{t(stats.key)}</h2>
        <a
          href={PAGES[stats.key]}
          className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft underline-offset-4 hover:underline"
        >
          {t('open')}
        </a>
      </div>
      {latest ? (
        <>
          <div className="mt-3 flex flex-wrap gap-2 font-mono text-sm">
            {(['high', 'medium', 'low'] as const).map(
              (k) =>
                c[k] !== undefined && (
                  <span key={k} className="rounded border-[1.5px] border-ink px-2 py-0.5">
                    {k} {c[k]}
                  </span>
                ),
            )}
            <span className="rounded border-[1.5px] border-ink bg-ink px-2 py-0.5 text-[var(--paper)]">
              total {c.total ?? 0}
            </span>
          </div>
          <Sparkline values={series} />
          <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            {records.length} {t('runs')} · {t('latest')}:{' '}
            {String(latest.timestamp ?? '').slice(0, 19)}
            {series.length >= 2 && ` · ${series[0]} → ${series[series.length - 1]}`}
          </p>
          <p className="font-mono text-[11px] text-muted">{t('trend')}</p>
        </>
      ) : (
        <p className="mt-3 text-sm text-muted">{t('empty')}</p>
      )}
    </Card>
  )
}

export default function App() {
  const [stats, setStats] = useState<AgentStats[]>([])

  useEffect(() => {
    let alive = true
    void Promise.all(AGENT_KEYS.map(fetchStats)).then((all) => {
      if (alive) setStats(all)
    })
    return () => {
      alive = false
    }
  }, [])

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / governance" maxW="max-w-[660px]" />
      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {stats.map((s) => (
          <AgentCard key={s.key} stats={s} />
        ))}
      </div>
    </div>
  )
}
