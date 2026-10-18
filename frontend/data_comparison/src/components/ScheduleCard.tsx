import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import i18n from '@/i18n'
import {
  scheduleStart,
  scheduleStatus,
  scheduleStop,
  type CompareOptions,
  type FeatureFields,
  type ScheduleStatus,
  type WebhookOptions,
} from '@/api'
import { Collapsible, inputCls, labelCls, smallBtnCls } from '@/components/Collapsible'

const lang = () => (i18n.language.startsWith('zh') ? 'zh' : 'en')

// Scheduled comparison (legacy accordion E, ui.py:1276) + webhook fields
// (legacy accordion X, ui.py:1292). The webhook URL / notify-on-fail ride
// on compare-all and schedule-start requests; posting stays server-side.
export function ScheduleCard({
  sessionId,
  tableA,
  tableB,
  options,
  intervals,
  webhook,
  onWebhook,
  featureFields,
  resetSeq,
}: {
  sessionId: string
  tableA: string
  tableB: string
  options: CompareOptions
  intervals: string[]
  webhook: WebhookOptions
  onWebhook: (w: WebhookOptions) => void
  featureFields?: () => FeatureFields
  resetSeq: number
}) {
  const { t } = useTranslation()
  const [interval, setInterval] = useState('15')

  // options reset restores the interval default (legacy 27-output reset,
  // inventory ui.py:2142-2151: schedule_interval→"15"); the running
  // schedule itself is untouched, like legacy.
  useEffect(() => {
    if (resetSeq > 0) setInterval('15')
  }, [resetSeq])
  const [status, setStatus] = useState<ScheduleStatus | null>(null)
  const [message, setMessage] = useState('')

  const refresh = async () => {
    try {
      setStatus(await scheduleStatus(sessionId))
    } catch {
      /* session not ready yet */
    }
  }

  const onStart = async () => {
    try {
      const r = await scheduleStart({
        session_id: sessionId,
        table_a: tableA,
        table_b: tableB,
        lang: lang(),
        ...options,
        ...featureFields?.(),
        ...webhook,
        interval,
      })
      setMessage(r.message)
      await refresh()
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : e}`)
    }
  }

  const onStop = async () => {
    try {
      const r = await scheduleStop(sessionId, lang())
      setMessage(r.message)
      await refresh()
    } catch (e) {
      setMessage(`❌ ${e instanceof Error ? e.message : e}`)
    }
  }

  return (
    <>
      <Collapsible title={t('webhook')} testId="webhook-card">
        <label className={labelCls}>{t('webhookUrl')}</label>
        <input
          data-testid="webhook-url"
          className={inputCls}
          placeholder={t('webhookUrlHint')}
          value={webhook.webhook_url}
          onChange={(e) => onWebhook({ ...webhook, webhook_url: e.target.value })}
        />
        <label className="mt-2 flex items-center gap-2 font-mono text-[12px] text-ink">
          <input
            data-testid="webhook-on-fail"
            type="checkbox"
            checked={webhook.notify_on_fail}
            onChange={(e) => onWebhook({ ...webhook, notify_on_fail: e.target.checked })}
          />
          {t('webhookOnFail')}
        </label>
      </Collapsible>

      <Collapsible title={t('schedule')} testId="schedule-card" onOpen={refresh}>
        <label className={labelCls}>{t('scheduleInterval')}</label>
        <select
          data-testid="schedule-interval"
          className={inputCls}
          value={interval}
          onChange={(e) => setInterval(e.target.value)}
        >
          {intervals.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <div className="mt-2 flex gap-2">
          <button
            data-testid="schedule-start"
            className={smallBtnCls}
            disabled={!sessionId || !(tableA && tableB)}
            onClick={onStart}
          >
            {t('scheduleStart')}
          </button>
          <button
            data-testid="schedule-stop"
            className={smallBtnCls}
            disabled={!sessionId}
            onClick={onStop}
          >
            {t('scheduleStop')}
          </button>
        </div>
        <div data-testid="schedule-status" className="mt-2 font-mono text-[12px] text-muted">
          {message && <p>{message}</p>}
          {status && (
            <p>
              {status.active ? `● ${t('scheduleActive')} — ${status.interval} min` : `○ ${t('scheduleInactive')}`}
              {status.last_run && ` · ${t('scheduleLastRun')}: ${status.last_run}`}
              {status.last_error && ` · ${t('scheduleLastError')}: ${status.last_error}`}
            </p>
          )}
        </div>
      </Collapsible>
    </>
  )
}
