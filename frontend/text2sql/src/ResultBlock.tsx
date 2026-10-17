import { useMemo, useRef, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { sendFeedback } from '@/api'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export interface ResultData {
  sql: string
  columns: string[]
  rows: unknown[][]
  row_count: number
  chart_type?: string | null
}

const PAGE = 50
const CHART_TYPES = ['bar', 'line', 'pie', 'scatter', 'none'] as const
// semantic chart palette (accent/ok are theme-exempt; others neutral grays)
const PIE_COLORS = ['var(--ink)', 'var(--accent)', 'var(--ok)', 'var(--muted)', 'var(--ink-soft)']

function toCsv(columns: string[], rows: unknown[][]): string {
  const esc = (v: unknown) => {
    const s = String(v ?? '')
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [columns.map(esc).join(','), ...rows.map((r) => r.map(esc).join(','))].join('\n')
}

function download(name: string, blob: Blob) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
}

function ChartView({ data, type }: { data: ResultData; type: (typeof CHART_TYPES)[number] }) {
  const points = useMemo(
    () =>
      data.rows.slice(0, 200).map((r) => ({
        x: String(r[0] ?? ''),
        y: Number(r[1] ?? 0),
      })),
    [data.rows],
  )
  const axis = {
    tick: { fill: 'var(--muted)', fontSize: 11, fontFamily: 'IBM Plex Mono' },
    axisLine: { stroke: 'var(--line)' },
    tickLine: false as const,
  }
  const tooltip = (
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
  )
  if (type === 'pie')
    return (
      <ResponsiveContainer width="100%" height={256}>
        <PieChart>
          {tooltip}
          <Pie data={points} dataKey="y" nameKey="x" outerRadius="80%">
            {points.map((_, i) => (
              <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    )
  if (type === 'line')
    return (
      <ResponsiveContainer width="100%" height={256}>
        <LineChart data={points}>
          <CartesianGrid stroke="var(--grid)" />
          <XAxis dataKey="x" {...axis} />
          <YAxis {...axis} />
          {tooltip}
          <Line dataKey="y" stroke="var(--ink)" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    )
  if (type === 'scatter')
    return (
      <ResponsiveContainer width="100%" height={256}>
        <ScatterChart>
          <CartesianGrid stroke="var(--grid)" />
          <XAxis dataKey="x" {...axis} />
          <YAxis dataKey="y" {...axis} />
          {tooltip}
          <Scatter data={points} fill="var(--ink)" />
        </ScatterChart>
      </ResponsiveContainer>
    )
  return (
    <ResponsiveContainer width="100%" height={256}>
      <BarChart data={points}>
        <CartesianGrid stroke="var(--grid)" />
        <XAxis dataKey="x" {...axis} />
        <YAxis {...axis} />
        {tooltip}
        <Bar dataKey="y" fill="var(--ink)" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function ResultBlock({
  data,
  sessionId,
  question,
}: {
  data: ResultData
  sessionId?: string
  question?: string
}) {
  const { t } = useTranslation()
  const [page, setPage] = useState(0)
  const [chartType, setChartType] = useState<(typeof CHART_TYPES)[number]>(
    (data.chart_type as (typeof CHART_TYPES)[number]) ?? 'none',
  )
  const chartRef = useRef<HTMLDivElement>(null)
  const [fb, setFb] = useState<'up' | 'down' | null>(null)

  const onFeedback = useCallback(
    async (positive: boolean) => {
      if (!sessionId || !question || fb) return
      try {
        await sendFeedback(sessionId, question, data.sql, positive)
        setFb(positive ? 'up' : 'down')
      } catch {
        /* best-effort */
      }
    },
    [sessionId, question, data.sql, fb],
  )

  const paged = data.rows.length > 20
  const pages = Math.max(1, Math.ceil(data.rows.length / PAGE))
  const shown = paged ? data.rows.slice(page * PAGE, (page + 1) * PAGE) : data.rows

  const exportPng = () => {
    const svg = chartRef.current?.querySelector('svg')
    if (!svg) return
    const xml = new XMLSerializer().serializeToString(svg)
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = svg.clientWidth * 2
      canvas.height = svg.clientHeight * 2
      const ctx = canvas.getContext('2d')!
      ctx.scale(2, 2)
      ctx.drawImage(img, 0, 0)
      canvas.toBlob((b) => b && download('chart.png', b))
    }
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml)
  }

  return (
    <div className="st-result space-y-2 overflow-x-auto">
      <pre className="rounded border border-line bg-paper px-2 py-1 font-mono text-[12px] text-muted">
        {data.sql}
      </pre>
      <table className="w-full font-mono text-[13px]">
        <thead>
          <tr className="border-b-2 border-ink text-left">
            {data.columns.map((c) => (
              <th key={c} className="px-2 py-1 text-ink">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((r, i) => (
            <tr key={i} className="border-b border-line last:border-b-0">
              {r.map((v, j) => (
                <td key={j} className="px-2 py-1 text-fg">
                  {String(v ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-3 font-mono text-[12px] text-muted">
        <span>{data.row_count} rows</span>
        {paged && (
          <span className="st-pager flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded border border-line px-2 disabled:opacity-40"
            >
              ←
            </button>
            {page + 1}/{pages}
            <button
              onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
              disabled={page >= pages - 1}
              className="rounded border border-line px-2 disabled:opacity-40"
            >
              →
            </button>
          </span>
        )}
        <button
          onClick={() =>
            download('result.csv', new Blob([toCsv(data.columns, data.rows)], { type: 'text/csv' }))
          }
          className="st-csv rounded border border-ink px-2 text-ink"
        >
          CSV
        </button>
        <select
          aria-label={t('chartType')}
          className="rounded border border-line bg-card px-1 py-0.5 text-fg"
          value={chartType}
          onChange={(e) => setChartType(e.target.value as (typeof CHART_TYPES)[number])}
        >
          {CHART_TYPES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        {chartType !== 'none' && (
          <button onClick={exportPng} className="rounded border border-ink px-2 text-ink">
            PNG
          </button>
        )}
        {sessionId && question && (
          <span className="ml-auto flex items-center gap-1">
            <button
              onClick={() => onFeedback(true)}
              disabled={fb !== null}
              className={
                'rounded border px-1.5 transition ' +
                (fb === 'up'
                  ? 'border-ink bg-ink text-paper'
                  : 'border-line text-muted hover:text-ink disabled:opacity-40')
              }
              title={t('thumbsUp')}
            >
              👍
            </button>
            <button
              onClick={() => onFeedback(false)}
              disabled={fb !== null}
              className={
                'rounded border px-1.5 transition ' +
                (fb === 'down'
                  ? 'border-accent bg-accent text-paper'
                  : 'border-line text-muted hover:text-accent disabled:opacity-40')
              }
              title={t('thumbsDown')}
            >
              👎
            </button>
            {fb && (
              <span className="text-[11px] text-muted">{t('feedbackSent')}</span>
            )}
          </span>
        )}
      </div>
      {chartType !== 'none' && data.rows.length > 1 && (
        <div ref={chartRef} className="st-chart w-full">
          <ChartView data={data} type={chartType} />
        </div>
      )}
    </div>
  )
}
