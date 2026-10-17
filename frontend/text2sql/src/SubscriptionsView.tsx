import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import {
  createSubscription,
  deleteSubscription,
  fetchSubscriptions,
  patchSubscription,
  runSubscription,
  type Subscription,
} from '@/api'

export function SubscriptionsView() {
  const { t } = useTranslation()
  const [subs, setSubs] = useState<Subscription[]>([])
  const [err, setErr] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: '',
    cron: '0 9 * * *',
    source_type: 'metric',
    metric: '',
    favorite_id: '',
    webhook_url: '',
  })

  const refresh = () => {
    fetchSubscriptions().then((r) => setSubs(r.subscriptions))
  }
  useEffect(refresh, [])

  const doCreate = async () => {
    try {
      await createSubscription(form)
      setForm({ name: '', cron: '0 9 * * *', source_type: 'metric', metric: '', favorite_id: '', webhook_url: '' })
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

  const doRun = async (id: string) => {
    try {
      const r = await runSubscription(id)
      if (r.status === 'error') setErr((r as any).error || 'run failed')
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
            <div className="flex gap-2">
              <label className="flex items-center gap-1 text-muted">
                <input
                  type="radio"
                  checked={form.source_type === 'metric'}
                  onChange={() => setForm({ ...form, source_type: 'metric' })}
                />
                {t('metrics')}
              </label>
              <label className="flex items-center gap-1 text-muted">
                <input
                  type="radio"
                  checked={form.source_type === 'favorite'}
                  onChange={() => setForm({ ...form, source_type: 'favorite' })}
                />
                {t('favorites')}
              </label>
            </div>
            {form.source_type === 'metric' ? (
              <input
                value={form.metric}
                onChange={(e) => setForm({ ...form, metric: e.target.value })}
                placeholder={t('metricName')}
                className="w-full rounded border border-line bg-card px-2 py-1 text-fg outline-none"
              />
            ) : (
              <input
                value={form.favorite_id}
                onChange={(e) => setForm({ ...form, favorite_id: e.target.value })}
                placeholder="Favorite ID"
                className="w-full rounded border border-line bg-card px-2 py-1 text-fg outline-none"
              />
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
                  {s.source_type === 'metric' ? s.metric : s.favorite_id}
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
      </Card>
    </div>
  )
}
