import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchSummary } from '@/api'
import type { SummaryResponse } from '@/api'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { fieldCls, labelCls, smallBtnCls } from '@shared/constants'
import { langOf } from '@shared/lang'
import { CostChart, TokensChart } from '@/Charts'
import { PriceTable } from '@/PriceTable'
import { downloadCsv, summaryCsv } from '@/csv'

const DAY_CHOICES = [7, 14, 30, 90]

// Mirrors the Gradio page's _usd (llm_cost/ui.py).
function usd(v: number): string {
  const opts =
    v < 1
      ? { minimumFractionDigits: 4, maximumFractionDigits: 4 }
      : { minimumFractionDigits: 2, maximumFractionDigits: 2 }
  return '$' + v.toLocaleString('en-US', opts)
}

export default function App() {
  const { t, i18n } = useTranslation()
  const lang = langOf(i18n)

  const [days, setDays] = useState(30)
  const [budget, setBudget] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [resp, setResp] = useState<SummaryResponse | null>(null)

  const budgetNum = budget.trim() === '' ? null : Number(budget)
  const budgetValid = budgetNum === null || (Number.isFinite(budgetNum) && budgetNum >= 0)

  const refresh = useCallback(() => {
    if (!budgetValid) return
    setLoading(true)
    fetchSummary(days, budgetNum, lang)
      .then((r) => {
        setResp(r)
        setError('')
      })
      .catch((e) => {
        setResp(null)
        setError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => setLoading(false))
  }, [days, budgetNum, lang, budgetValid])

  // Load on mount and auto-refresh on days/budget change — mirrors the
  // Gradio page's _on_load + days.change/budget.change wiring.
  useEffect(() => {
    refresh()
  }, [refresh])

  const cost = resp ? Number(resp.summary.total.cost_usd) : 0
  const banner =
    resp && budgetNum !== null && budgetNum > 0
      ? t(resp.over_budget ? 'budgetOver' : 'budgetOk', {
          cost: usd(cost),
          budget: usd(budgetNum),
          pct: Math.round((cost / budgetNum) * 100) + '%',
        })
      : ''
  const csv = resp ? summaryCsv(resp.summary) : null

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-10">
      <PageHeader badge="ai / llmcost" />

      <div className="mt-8 flex flex-wrap items-end gap-4">
        <label className="w-36">
          <span className={labelCls}>{t('daysLabel')}</span>
          <select
            className={fieldCls}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            {DAY_CHOICES.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label className="w-48">
          <span className={labelCls}>{t('budgetLabel')}</span>
          <input
            type="number"
            min={0}
            step="any"
            className={fieldCls}
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
          />
        </label>
        <button
          onClick={refresh}
          disabled={loading}
          className="rounded border-[1.5px] border-ink bg-ink px-6 py-2 font-mono text-sm text-paper transition enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard disabled:opacity-50"
        >
          {t('refreshBtn')}
        </button>
        {csv !== null && (
          <button className={smallBtnCls + ' py-2.5'} onClick={() => downloadCsv(csv)}>
            {t('csvBtn')}
          </button>
        )}
      </div>

      <Card className="mt-6">
        {loading ? (
          <p className="font-mono text-sm text-muted">{t('loading')}</p>
        ) : error ? (
          <p className="font-mono text-sm text-ink">⚠️ {error}</p>
        ) : resp ? (
          <>
            {banner && (
              <p
                className={`mb-4 rounded border-[1.5px] px-3 py-2 font-mono text-sm ${
                  resp.over_budget
                    ? 'border-[#e11d48] text-[#e11d48]'
                    : 'border-[#16a34a] text-[#16a34a]'
                }`}
              >
                {banner}
              </p>
            )}
            {resp.summary.total.calls === 0 && (
              <p className="mb-4 font-mono text-sm text-muted">{t('noData')}</p>
            )}
            <ReportView className="lc-report" markdown={resp.report ?? ''} />
            {resp.summary.total.calls > 0 && (
              <div className="mt-6 grid gap-6 md:grid-cols-2">
                <CostChart summary={resp.summary} budget={budgetNum} />
                <TokensChart summary={resp.summary} />
              </div>
            )}
          </>
        ) : null}
      </Card>

      <PriceTable />
    </div>
  )
}
