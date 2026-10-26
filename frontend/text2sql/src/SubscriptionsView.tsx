import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import {
  backtestSubscription,
  createSubscription,
  deleteSubscription,
  fetchSubscriptions,
  patchSubscription,
  runSubscription,
  type BacktestResult,
  type Subscription,
} from '@/api'

export function SubscriptionsView() {
  const { t } = useTranslation()
  const [subs, setSubs] = useState<Subscription[]>([])
  const [err, setErr] = useState('')
  const [showForm, setShowForm] = useState(false)
  const emptyForm = {
    name: '',
    cron: '0 9 * * *',
    source_type: 'metric',
    metric: '',
    favorite_id: '',
    webhook_url: '',
    threshold_pct: '10',
    watch_mode: 'dod',
    max_lag_days: '1',
    metrics: '',
  }
  const [form, setForm] = useState(emptyForm)

  const refresh = () => {
    fetchSubscriptions().then((r) => setSubs(r.subscriptions))
  }
  useEffect(refresh, [])

  const doCreate = async () => {
    try {
      await createSubscription({
        name: form.name,
        cron: form.cron,
        source_type: form.source_type,
        metric: form.metric,
        favorite_id: form.favorite_id,
        webhook_url: form.webhook_url,
        threshold_pct: Number(form.threshold_pct) || 10,
        watch_mode: form.watch_mode,
        max_lag_days: Number(form.max_lag_days) || 1,
        metrics: form.metrics.split(',').map((s) => s.trim()).filter(Boolean),
      })
      setForm(emptyForm)
      setShowForm(false)
      refresh()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const doToggle = async (id: string, enabled: boolean) => {
    await patchSubscription(id, !enabled)
    refresh()
  }

  const [backtest, setBacktest] = useState<
    { name: string; result: BacktestResult } | null
  >(null)
  const [backtesting, setBacktesting] = useState('')

  const doBacktest = async (s: Subscription) => {
    setErr('')
    setBacktesting(s.id)
    try {
      const result = await backtestSubscription(s.id)
      setBacktest({ name: s.name, result })
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBacktesting('')
    }
  }

  const doRun = async (id: string) => {
    try {
      const r = await runSubscription(id)
      if (r.status === 'error') setErr(r.error || 'run failed')
      refresh()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="st-subscriptions-view space-y-4">
      <Card>
        <div className="mb-2 flex items-center gap-3 font-mono text-[12px]">
          <span className="uppercase tracking-[0.18em] text-ink-soft">{t('subsTitle')}</span>
          <button onClick={refresh} className="rounded border border-line px-2 text-muted">
            ⟳
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="ml-auto rounded border border-ink px-3 text-ink hover:bg-ink hover:text-paper"
          >
            {showForm ? '✕' : t('createSub')}
          </button>
        </div>

        {showForm && (
          <div className="mb-3 space-y-2 rounded border border-line bg-paper p-3 font-mono text-[12px]">
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder={t('subName')}
              className="w-full rounded border border-line bg-card px-2 py-1 text-fg outline-none"
            />
            <input
              value={form.cron}
              onChange={(e) => setForm({ ...form, cron: e.target.value })}
              placeholder="cron (e.g. 0 9 * * *)"
              className="w-full rounded border border-line bg-card px-2 py-1 text-fg outline-none"
            />
            <div className="flex flex-wrap gap-2">
              {(
                [
                  ['metric', t('metrics')],
                  ['favorite', t('favorites')],
                  ['metric_watch', t('subWatch')],
                  ['freshness', t('subFreshness')],
                  ['digest', t('subDigest')],
                ] as const
              ).map(([value, label]) => (
                <label key={value} className="flex items-center gap-1 text-muted">
                  <input
                    type="radio"
                    checked={form.source_type === value}
                    onChange={() => setForm({ ...form, source_type: value })}
                  />
                  {label}
                </label>
              ))}
            </div>
            {form.source_type === 'favorite' ? (
              <input
                value={form.favorite_id}
                onChange={(e) => setForm({ ...form, favorite_id: e.target.value })}
                placeholder="Favorite ID"
                className="w-full rounded border border-line bg-card px-2 py-1 text-fg outline-none"
              />
            ) : form.source_type === 'digest' ? (
              <input
                value={form.metrics}
                onChange={(e) => setForm({ ...form, metrics: e.target.value })}
                placeholder={t('digestMetrics')}
                className="w-full rounded border border-line bg-card px-2 py-1 text-fg outline-none"
              />
            ) : (
              <input
                value={form.metric}
                onChange={(e) => setForm({ ...form, metric: e.target.value })}
                placeholder={t('metricName')}
                className="w-full rounded border border-line bg-card px-2 py-1 text-fg outline-none"
              />
            )}
            {form.source_type === 'metric_watch' && (
              <div className="flex items-center gap-2">
                <select
                  value={form.watch_mode}
                  onChange={(e) => setForm({ ...form, watch_mode: e.target.value })}
                  className="rounded border border-line bg-card px-2 py-1 text-fg outline-none"
                >
                  <option value="dod">{t('watchDod')}</option>
                  <option value="wow">{t('watchWow')}</option>
                  <option value="model">{t('watchModel')}</option>
                </select>
                {form.watch_mode !== 'model' && (
                  <label className="flex items-center gap-1 text-muted">
                    {t('watchThreshold')}
                    <input
                      value={form.threshold_pct}
                      onChange={(e) => setForm({ ...form, threshold_pct: e.target.value })}
                      className="w-16 rounded border border-line bg-card px-2 py-1 text-fg outline-none"
                    />
                    %
                  </label>
                )}
              </div>
            )}
            {form.source_type === 'freshness' && (
              <label className="flex items-center gap-1 text-muted">
                {t('freshLag')}
                <input
                  value={form.max_lag_days}
                  onChange={(e) => setForm({ ...form, max_lag_days: e.target.value })}
                  className="w-16 rounded border border-line bg-card px-2 py-1 text-fg outline-none"
                />
                {t('freshDays')}
              </label>
            )}
            <input
              value={form.webhook_url}
              onChange={(e) => setForm({ ...form, webhook_url: e.target.value })}
              placeholder="Webhook URL"
              className="w-full rounded border border-line bg-card px-2 py-1 text-fg outline-none"
            />
            <button
              onClick={doCreate}
              className="rounded border border-ink bg-ink px-4 py-1 text-paper"
            >
              {t('createSub')}
            </button>
          </div>
        )}

        <table className="w-full font-mono text-[13px]">
          <thead>
            <tr className="border-b-2 border-ink text-left">
              <th className="px-2 py-1 text-ink">{t('subName')}</th>
              <th className="px-2 py-1 text-ink">Cron</th>
              <th className="px-2 py-1 text-ink">{t('source')}</th>
              <th className="px-2 py-1 text-ink">{t('status')}</th>
              <th className="px-2 py-1 text-ink" />
            </tr>
          </thead>
          <tbody>
            {subs.map((s) => (
              <tr key={s.id} className="border-b border-line last:border-b-0">
                <td className="px-2 py-1 text-fg">{s.name}</td>
                <td className="px-2 py-1 text-muted">{s.cron}</td>
                <td className="px-2 py-1 text-muted">
                  {s.source_type === 'favorite'
                    ? s.favorite_id
                    : s.source_type === 'digest'
                      ? (s.metrics || []).join(',') || '*'
                      : `${s.metric}${s.source_type === 'metric_watch' ? ' ⚡' : s.source_type === 'freshness' ? ' ⏰' : ''}`}
                </td>
                <td className="px-2 py-1">
                  <span style={{ color: s.last_status === 'ok' ? 'var(--ok)' : s.last_status ? 'var(--accent)' : 'var(--muted)' }}>
                    {s.enabled ? (s.last_status || '—') : 'disabled'}
                  </span>
                </td>
                <td className="px-2 py-1">
                  <div className="flex gap-1">
                    <button
                      onClick={() => doToggle(s.id, s.enabled)}
                      className="rounded border border-line px-1.5 text-muted hover:text-ink"
                      title={s.enabled ? 'Disable' : 'Enable'}
                    >
                      {s.enabled ? '⏸' : '▶'}
                    </button>
                    <button
                      onClick={() => doRun(s.id)}
                      className="rounded border border-line px-1.5 text-muted hover:text-ink"
                      title="Run now"
                    >
                      ⚡
                    </button>
                    {s.source_type === 'metric_watch' && (
                      <button
                        onClick={() => doBacktest(s)}
                        className="rounded border border-line px-1.5 text-muted hover:text-ink"
                        title={t('backtest')}
                        disabled={backtesting === s.id}
                      >
                        {backtesting === s.id ? '…' : '📈'}
                      </button>
                    )}
                    <button
                      onClick={() => deleteSubscription(s.id).then(refresh)}
                      className="rounded border border-line px-1.5 text-muted hover:text-accent"
                    >
                      ✕
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {subs.length === 0 && !showForm && (
          <div className="py-4 text-center font-mono text-[13px] text-muted">—</div>
        )}
        {err && <div className="mt-2 font-mono text-[12px] text-accent">{err}</div>}
        {backtest && (
          <div className="mt-3 rounded border border-line bg-paper p-3 font-mono text-[12px]">
            <div className="mb-1 flex items-center gap-2">
              <span className="text-ink">
                📈 {backtest.name} · {t('backtestSummary', {
                  count: backtest.result.alert_count,
                  days: backtest.result.days_evaluated,
                })}
                {backtest.result.alert_rate_pct !== null &&
                  ` (${backtest.result.alert_rate_pct}%)`}
              </span>
              <button
                onClick={() => setBacktest(null)}
                className="ml-auto rounded border border-line px-1.5 text-muted"
              >
                ✕
              </button>
            </div>
            <div className="text-muted">
              {backtest.result.window.start} ~ {backtest.result.window.end} ·{' '}
              {backtest.result.watch_mode}
            </div>
            {backtest.result.alerts.slice(0, 10).map((a) => (
              <div key={a.day} className="text-muted">
                {a.day} · {a.actual.toLocaleString()}
                {a.expected !== undefined
                  ? ` (${t('backtestExpected')} ${a.expected.toLocaleString()} [${a.lo?.toLocaleString()}, ${a.hi?.toLocaleString()}])`
                  : a.change_rate_pct != null
                    ? ` (${a.change_rate_pct > 0 ? '+' : ''}${a.change_rate_pct}%)`
                    : ''}
              </div>
            ))}
            {backtest.result.alerts.length > 10 && (
              <div className="text-muted">… +{backtest.result.alerts.length - 10}</div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
