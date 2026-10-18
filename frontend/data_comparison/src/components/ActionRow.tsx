import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { compareAction, type CompareOptions, type CoreAction } from '@/api'
import { Card } from '@shared/components/card'

const ACTIONS: { action: CoreAction; labelKey: string }[] = [
  { action: 'schema', labelKey: 'actionSchema' },
  { action: 'count', labelKey: 'actionCount' },
  { action: 'sample', labelKey: 'actionSample' },
  { action: 'aggregate', labelKey: 'actionAggregate' },
]

export function ActionRow({
  sessionId,
  tableA,
  tableB,
  options,
  onResult,
}: {
  sessionId: string
  tableA: string
  tableB: string
  options: CompareOptions
  onResult: (html: string) => void
}) {
  const { t, i18n } = useTranslation()
  const [busy, setBusy] = useState<CoreAction | null>(null)

  const ready = Boolean(sessionId && tableA && tableB)

  const run = async (action: CoreAction) => {
    setBusy(action)
    try {
      const html = await compareAction(action, {
        session_id: sessionId,
        table_a: tableA,
        table_b: tableB,
        lang: i18n.language.startsWith('zh') ? 'zh' : 'en',
        ...options,
      })
      onResult(html)
    } catch (e) {
      onResult(
        `<div style="color:var(--accent);font-family:monospace;font-size:13px;">❌ ${
          e instanceof Error ? e.message : String(e)
        }</div>`,
      )
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card>
      <div className="grid grid-cols-2 gap-2" data-testid="action-row">
        {ACTIONS.map(({ action, labelKey }) => (
          <button
            key={action}
            data-testid={`action-${action}`}
            onClick={() => run(action)}
            disabled={!ready || busy !== null}
            className="rounded border-[1.5px] border-ink px-3 py-1.5 font-mono text-[13px] text-ink transition enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard disabled:opacity-40"
          >
            {busy === action ? t('running') : t(labelKey)}
          </button>
        ))}
      </div>
    </Card>
  )
}
