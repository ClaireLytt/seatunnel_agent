import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { RunCounts } from '@/api'

const ORDER = ['PASS', 'HEALED', 'FAIL', 'ERROR', 'SKIP', 'MANUAL'] as const

const COLOR: Record<string, string> = {
  PASS: 'var(--ok)',
  HEALED: 'var(--ink-soft)',
  FAIL: 'var(--accent)',
  ERROR: 'var(--accent)',
  SKIP: 'var(--muted)',
  MANUAL: 'var(--muted)',
}

export function CountsChart({ counts }: { counts: RunCounts }) {
  const data = ORDER.map((k) => ({ name: k, value: counts[k] ?? 0 }))
  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
        <XAxis
          dataKey="name"
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
        <Bar dataKey="value" radius={[2, 2, 0, 0]}>
          {data.map((d) => (
            <Cell key={d.name} fill={COLOR[d.name]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
