// Cost / tokens charts — mirrors the Gradio page's matplotlib figures
// (_cost_figure / _tokens_figure in agents/ai/llm_cost/ui.py).
// Colors follow the llm_eval TrendChart precedent: theme tokens only.
import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Summary } from '@/api'

const PALETTE = ['var(--ink)', 'var(--accent)', 'var(--ok)', 'var(--ink-soft)', 'var(--muted)']

const tickStyle = { fill: 'var(--muted)', fontSize: 10, fontFamily: 'IBM Plex Mono' }
const tooltipStyle = {
  background: 'var(--card)',
  border: '1px solid var(--line)',
  borderRadius: 3,
  fontFamily: 'IBM Plex Mono',
  fontSize: 12,
  color: 'var(--fg)',
}

// Stacked per-day cost bars, one segment per model; optional dashed
// daily-budget line (window budget / window days) — _cost_figure parity.
export function CostChart({ summary, budget }: { summary: Summary; budget: number | null }) {
  const { t } = useTranslation()
  const byDayModel = summary.by_day_model ?? {}
  const days = Object.keys(byDayModel).sort().slice(-30)
  const models = [...new Set(days.flatMap((d) => Object.keys(byDayModel[d])))].sort()
  if (days.length === 0 || models.length === 0) return null
  const data = days.map((d) => ({ day: d, ...byDayModel[d] }))
  const daily = budget && budget > 0 && summary.days ? budget / summary.days : null
  return (
    <figure>
      <figcaption className="mb-1 font-mono text-xs uppercase tracking-[0.12em] text-ink-soft">
        {t('chartCost')}
      </figcaption>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <XAxis
            dataKey="day"
            tick={tickStyle}
            axisLine={{ stroke: 'var(--line)' }}
            tickLine={false}
          />
          <YAxis tick={tickStyle} axisLine={{ stroke: 'var(--line)' }} tickLine={false} unit="" />
          <Tooltip
            cursor={{ fill: 'var(--grid)' }}
            contentStyle={tooltipStyle}
            formatter={(v) => `$${Number(v).toFixed(4)}`}
          />
          <Legend wrapperStyle={{ fontFamily: 'IBM Plex Mono', fontSize: 11 }} />
          {models.map((m, i) => (
            <Bar
              key={m}
              dataKey={m}
              stackId="cost"
              fill={PALETTE[i % PALETTE.length]}
              stroke="var(--card)"
              strokeWidth={1}
              isAnimationActive={false}
            />
          ))}
          {daily !== null && (
            <ReferenceLine
              y={daily}
              stroke="var(--ink-soft)"
              strokeDasharray="5 4"
              label={{
                value: t('budgetLine'),
                position: 'insideTopLeft',
                fill: 'var(--muted)',
                fontSize: 10,
                fontFamily: 'IBM Plex Mono',
              }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}

// Per-model input/output stacked tokens — _tokens_figure parity (top 8).
export function TokensChart({ summary }: { summary: Summary }) {
  const { t } = useTranslation()
  const byModel = summary.by_model ?? {}
  const models = Object.keys(byModel)
    .sort((a, b) => byModel[b].input + byModel[b].output - (byModel[a].input + byModel[a].output))
    .slice(0, 8)
  if (models.length === 0) return null
  const data = models.map((m) => ({
    model: m,
    input: byModel[m].input,
    output: byModel[m].output,
  }))
  return (
    <figure>
      <figcaption className="mb-1 font-mono text-xs uppercase tracking-[0.12em] text-ink-soft">
        {t('chartTokens')}
      </figcaption>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
          <XAxis
            dataKey="model"
            tick={tickStyle}
            axisLine={{ stroke: 'var(--line)' }}
            tickLine={false}
            interval={0}
          />
          <YAxis tick={tickStyle} axisLine={{ stroke: 'var(--line)' }} tickLine={false} />
          <Tooltip cursor={{ fill: 'var(--grid)' }} contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontFamily: 'IBM Plex Mono', fontSize: 11 }} />
          <Bar
            dataKey="input"
            stackId="tok"
            fill="var(--ink)"
            stroke="var(--card)"
            strokeWidth={1}
            isAnimationActive={false}
          />
          <Bar
            dataKey="output"
            stackId="tok"
            fill="var(--accent)"
            stroke="var(--card)"
            strokeWidth={1}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
