import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { DailyStat } from '@/api'

// Findings per day, stacked by severity — replaces the legacy matplotlib
// figure. Severity colors come from the theme tokens (same vocabulary as the
// uitest counts chart): accent for bad, ok for good, neutral for middle.
const SEVERITIES = [
  { key: 'critical', color: 'var(--accent)' },
  { key: 'risk', color: 'var(--ink-soft)' },
  { key: 'suggestion', color: 'var(--ok)' },
] as const

export function TrendChart({ daily }: { daily: DailyStat[] }) {
  const data = daily.slice(-14)
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
        <XAxis
          dataKey="day"
          tick={{ fill: 'var(--muted)', fontSize: 11, fontFamily: 'IBM Plex Mono' }}
          axisLine={{ stroke: 'var(--line)' }}
          tickLine={false}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fill: 'var(--muted)', fontSize: 11, fontFamily: 'IBM Plex Mono' }}
          axisLine={{ stroke: 'var(--line)' }}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: 'var(--grid)' }}
          contentStyle={{
            background: 'var(--card)',
            border: '1px solid var(--line)',
            borderRadius: 3,
            fontFamily: 'IBM Plex Mono',
            fontSize: 12,
            color: 'var(--fg)',
          }}
        />
        {SEVERITIES.map((s) => (
          <Bar key={s.key} dataKey={s.key} stackId="sev" fill={s.color} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
