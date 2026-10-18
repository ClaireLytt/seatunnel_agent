import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  compareProfile,
  compareStream,
  type CompareOptions,
  type FeatureFields,
  type StreamAction,
  type WebhookOptions,
} from '@/api'
import { Card } from '@shared/components/card'

type CompoundAction = StreamAction | 'profile'

const ACTIONS: { action: CompoundAction; labelKey: string; needsTables: boolean }[] = [
  { action: 'all', labelKey: 'actionCompareAll', needsTables: true },
  { action: 'profile', labelKey: 'actionProfile', needsTables: true },
  { action: 'batch-count', labelKey: 'actionBatchCount', needsTables: false },
  { action: 'batch-full', labelKey: 'actionBatchFull', needsTables: false },
]

export function CompoundRow({
  sessionId,
  tableA,
  tableB,
  options,
  onResult,
  featureFields,
  webhook,
}: {
  sessionId: string
  tableA: string
  tableB: string
  options: CompareOptions
  onResult: (html: string) => void
  // optional compare-all stages (skew/checksum/partition/custom agg)
  featureFields?: () => FeatureFields
  // webhook fields ride on compare-all (ticket 09); posting is server-side
  webhook?: WebhookOptions
}) {
  const { t, i18n } = useTranslation()
  const [busy, setBusy] = useState<CompoundAction | null>(null)
  const [progress, setProgress] = useState<{ value: number; desc: string } | null>(null)

  const run = async (action: CompoundAction) => {
    if (busy !== null) return // double-trigger guard (server also 409s)
    setBusy(action)
    setProgress(null)
    try {
      const params = {
        session_id: sessionId,
        table_a: tableA,
        table_b: tableB,
        lang: i18n.language.startsWith('zh') ? 'zh' : 'en',
        ...options,
        ...(action === 'all' ? featureFields?.() : undefined),
        ...(action === 'all' ? webhook : undefined),
      }
      const html =
        action === 'profile'
          ? await compareProfile(params)
          : await compareStream(action, params, (value, desc) =>
              setProgress({ value, desc }),
            )
      onResult(html)
    } catch (e) {
      onResult(
        `<div style="color:var(--accent);font-family:monospace;font-size:13px;">❌ ${
          e instanceof Error ? e.message : String(e)
        }</div>`,
      )
    } finally {
      setBusy(null)
      setProgress(null)
    }
  }

  return (
    <Card>
      <div className="grid grid-cols-2 gap-2" data-testid="compound-row">
        {ACTIONS.map(({ action, labelKey, needsTables }) => (
          <button
            key={action}
            data-testid={`action-${action}`}
            onClick={() => run(action)}
            disabled={
              busy !== null || !sessionId || (needsTables && !(tableA && tableB))
            }
            className="rounded border-[1.5px] border-ink px-3 py-1.5 font-mono text-[13px] text-ink transition enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard disabled:opacity-40"
          >
            {busy === action ? t('running') : t(labelKey)}
          </button>
        ))}
      </div>
      {progress && (
        <div className="mt-3" data-testid="compound-progress">
          <div className="h-1.5 overflow-hidden rounded-full bg-ink-soft/20">
            <div
              className="h-full rounded-full bg-ink transition-[width] duration-300"
              style={{ width: `${Math.round(progress.value * 100)}%` }}
            />
          </div>
          <p className="mt-1 font-mono text-[11px] text-muted">
            {progress.desc || t('running')}
          </p>
        </div>
      )}
    </Card>
  )
}
