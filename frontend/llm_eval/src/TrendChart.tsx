// Score trend line chart — one line per suite, last 20 runs each
// (mirrors the Gradio page's _trend_figure in agents/ai/llm_eval/ui.py).
// Colors follow the uitest CountsChart precedent: theme tokens only.
import {
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { HistoryRun } from '@/api'

const PALETTE = [
  'var(--ink)',
  'var(--accent)',
  'var(--ok)',
  'var(--ink-soft)',
  'var(--muted)',
]

export function TrendChart({ runs }: { runs: HistoryRun[] }) {
  const bySuite = new Map<string, { ts: string; score: number }[]>()
  for (const r of runs) {
    const suite = r.suite || '?'
    const pts = bySuite.get(suite) ?? []
    pts.push({ ts: (r.ts ?? '').slice(0, 16), score: Number(r.score ?? 0) })
    bySuite.set(suite, pts)
  }
  const suites = [...bySuite.keys()].sort()
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <XAxis
          dataKey="ts"
          type="category"
          allowDuplicatedCategory={false}
          tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
          axisLine={{ stroke: 'var(--line)' }}
          tickLine={false}
        />
        <YAxis
          domain={[0, 1.05]}
          tick={{ fill: 'var(--muted)', fontSize: 11, fontFamily: 'IBM Plex Mono' }}
          axisLine={{ stroke: 'var(--line)' }}
          tickLine={false}
        />
        <Tooltip
          cursor={{ stroke: 'var(--grid)' }}
          contentStyle={{
            background: 'var(--card)',
            border: '1px solid var(--line)',
            borderRadius: 3,
            fontFamily: 'IBM Plex Mono',
            fontSize: 12,
            color: 'var(--fg)',
          }}
        />
        <Legend wrapperStyle={{ fontFamily: 'IBM Plex Mono', fontSize: 11 }} />
        {suites.map((suite, i) => (
          <Line
            key={suite}
            data={bySuite.get(suite)!.slice(-20)}
            dataKey="score"
            name={suite}
            stroke={PALETTE[i % PALETTE.length]}
            strokeWidth={1.5}
            dot={{ r: 2.5, fill: PALETTE[i % PALETTE.length] }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
