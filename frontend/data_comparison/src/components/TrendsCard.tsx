import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Bar,
  BarChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import i18n from '@/i18n'
import { fetchTrends, type TrendEntry } from '@/api'
import { Collapsible, inputCls, labelCls, smallBtnCls } from '@/components/Collapsible'

const lang = () => (i18n.language.startsWith('zh') ? 'zh' : 'en')

// History trends (legacy accordion H, ui.py:818): the matplotlib PNG is
// replaced by recharts panels fed by GET /trends; alert evaluation stays
// server-side and its card arrives as HTML.
// Accepted presentational deviation: the legacy figure drew mismatches and
// schema_changes as two separate subplots; here they are one grouped
// BarChart (same data, same series labels).
const axisTick = { fill: 'var(--muted)', fontSize: 10, fontFamily: 'IBM Plex Mono' }
const axisLine = { stroke: 'var(--line)' }
const tooltipStyle = {
  background: 'var(--card)',
  border: '1px solid var(--line)',
  borderRadius: 3,
  fontFamily: 'IBM Plex Mono',
  fontSize: 12,
  color: 'var(--fg)',
}

function Panel({ label, children }: { label: string; children: React.ReactElement }) {
  return (
    <div className="mt-3">
      <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-soft">
        {label}
      </p>
      <ResponsiveContainer width="100%" height={140}>
        {children}
      </ResponsiveContainer>
    </div>
  )
}

export function TrendsCard({ resetSeq }: { resetSeq: number }) {
  const { t } = useTranslation()
  const [rules, setRules] = useState('')

  // options reset also clears the alert rules (legacy 27-output reset,
  // inventory ui.py:2142-2151)
  useEffect(() => {
    if (resetSeq > 0) setRules('')
  }, [resetSeq])
  const [entries, setEntries] = useState<TrendEntry[] | null>(null)
  const [alertsHtml, setAlertsHtml] = useState('')
  const [error, setError] = useState('')

  const onShow = async () => {
    try {
      const r = await fetchTrends(lang(), rules)
      setEntries(r.entries)
      setAlertsHtml(r.alerts_html)
      setError('')
    } catch (e) {
      setError(`❌ ${e instanceof Error ? e.message : e}`)
    }
  }

  const hasSkew = entries?.some((e) => e.skew_top1 !== null) ?? false

  return (
    <Collapsible title={t('trends')} testId="trends-card">
      <label className={labelCls}>{t('alertRules')}</label>
      <input
        data-testid="alert-rules"
        className={inputCls}
        placeholder={t('alertRulesHint')}
        value={rules}
        onChange={(e) => setRules(e.target.value)}
      />
      <button data-testid="trend-show" className={`${smallBtnCls} mt-2`} onClick={onShow}>
        {t('trendShow')}
      </button>
      {error && <p className="mt-2 font-mono text-[12px] text-muted">{error}</p>}
      {entries !== null &&
        (entries.length === 0 ? (
          <p className="mt-2 font-mono text-[12px] text-muted" data-testid="trend-empty">
            {t('trendNoData')}
          </p>
        ) : (
          <div data-testid="trend-charts">
            <p className="mt-2 font-mono text-[12px] text-muted">
              {t('trendRecords', { n: entries.length })}
            </p>
            <Panel label={t('trendDelta')}>
              <LineChart data={entries} margin={{ top: 4, right: 8, bottom: 0, left: -24 }}>
                <XAxis dataKey="timestamp" tick={axisTick} axisLine={axisLine} tickLine={false} />
                <YAxis tick={axisTick} axisLine={axisLine} tickLine={false} />
                <Tooltip cursor={{ stroke: 'var(--line)' }} contentStyle={tooltipStyle} />
                <ReferenceLine y={0} stroke="var(--ink-soft)" strokeDasharray="4 4" />
                <Line
                  type="monotone"
                  dataKey="delta"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  dot={{ r: 2.5, fill: 'var(--accent)' }}
                />
              </LineChart>
            </Panel>
            <Panel label={`${t('trendMismatches')} / ${t('trendSchema')}`}>
              <BarChart data={entries} margin={{ top: 4, right: 8, bottom: 0, left: -24 }}>
                <XAxis dataKey="timestamp" tick={axisTick} axisLine={axisLine} tickLine={false} />
                <YAxis allowDecimals={false} tick={axisTick} axisLine={axisLine} tickLine={false} />
                <Tooltip cursor={{ fill: 'var(--grid)' }} contentStyle={tooltipStyle} />
                <Bar dataKey="mismatches" name={t('trendMismatches')} fill="var(--ink-soft)" />
                <Bar dataKey="schema_changes" name={t('trendSchema')} fill="var(--ok)" />
              </BarChart>
            </Panel>
            {hasSkew && (
              <Panel label={t('trendSkew')}>
                <LineChart data={entries} margin={{ top: 4, right: 8, bottom: 0, left: -24 }}>
                  <XAxis dataKey="timestamp" tick={axisTick} axisLine={axisLine} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={axisTick} axisLine={axisLine} tickLine={false} />
                  <Tooltip cursor={{ stroke: 'var(--line)' }} contentStyle={tooltipStyle} />
                  <ReferenceLine y={50} stroke="var(--accent)" strokeDasharray="4 4" />
                  <Line
                    type="monotone"
                    dataKey="skew_top1"
                    connectNulls
                    stroke="var(--ink-soft)"
                    strokeWidth={2}
                    dot={{ r: 2.5, fill: 'var(--ink-soft)' }}
                  />
                </LineChart>
              </Panel>
            )}
          </div>
        ))}
      {alertsHtml && (
        <div
          data-testid="trend-alerts"
          className="mt-3 overflow-x-auto"
          dangerouslySetInnerHTML={{ __html: alertsHtml }}
        />
      )}
    </Collapsible>
  )
}
