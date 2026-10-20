import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchSummary } from '@/api'
import type { SummaryResponse } from '@/api'
import { Card } from '@shared/components/card'
import { ReportView } from '@shared/components/ReportView'
import { fieldCls, labelCls } from '@shared/constants'

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
  const lang = i18n.language.startsWith('zh') ? 'zh' : 'en'

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

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-10">
      <header className="flex items-start justify-between gap-4">
        <div>
          <span className="mb-4 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            ai / llmcost
          </span>
          <h1 className="font-display text-4xl font-bold tracking-tight text-ink">
            {t('title')}
          </h1>
          <p className="mt-3 max-w-[680px] text-muted">{t('subtitle')}</p>
        </div>
        <a
          href="/"
          title={t('home')}
          className="shrink-0 rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
        >
          {t('home')}
        </a>
      </header>

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
          </>
        ) : null}
      </Card>
    </div>
  )
}
