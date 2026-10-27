import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { skewDrift, type DriftItem } from '@/api'

import { smallBtnCls as btnCls } from '@/ui'

const BADGE: Record<DriftItem['verdict'], string> = {
  drift: 'bg-red-600/15 text-red-700 dark:text-red-400',
  stable: 'bg-green-600/15 text-green-700 dark:text-green-400',
  insufficient: 'bg-stone-500/15 text-muted',
}

export function DriftCard() {
  const { t, i18n } = useTranslation()
  const [items, setItems] = useState<DriftItem[]>([])
  const [empty, setEmpty] = useState(false)
  const [loaded, setLoaded] = useState(false)

  const refresh = async () => {
    setLoaded(true)
    try {
      const got = await skewDrift(i18n.language)
      setItems(got)
      setEmpty(got.length === 0)
    } catch {
      setItems([])
      setEmpty(true)
    }
  }

  return (
    <Card>
      <details
        onToggle={(e) => {
          if ((e.target as HTMLDetailsElement).open && !loaded) void refresh()
        }}
      >
        <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
          {t('drf_accordion')}
        </summary>
        <div className="mt-3 flex flex-col gap-3">
          <div>
            <button onClick={refresh} className={btnCls}>
              {t('drf_refresh')}
            </button>
          </div>
          {empty && <p className="text-sm italic text-muted">{t('drf_empty')}</p>}
          {items.map((it) => (
            <div key={it.table} className="flex flex-col gap-1 text-sm">
              <div className="flex items-center gap-2">
                <span
                  className={`rounded px-2 py-0.5 font-mono text-[11px] uppercase ${BADGE[it.verdict]}`}
                >
                  {t(`drf_${it.verdict}`)}
                </span>
                <span className="font-mono">{it.table}</span>
                {it.column && <span className="text-muted">key={it.column}</span>}
                <span className="text-muted">{t('drf_samples', { n: it.samples })}</span>
              </div>
              {it.verdict === 'drift' && it.hot_value?.changed && (
                <div className="pl-2 font-mono text-xs text-amber-700 dark:text-amber-400">
                  {t('drf_hot')}: {it.hot_value.prev} → {it.hot_value.cur}
                </div>
              )}
              {it.drifts.map((d) => (
                <div key={d.metric} className="pl-2 font-mono text-xs text-muted">
                  {d.metric}: {d.baseline} → {d.current} (
                  {d.delta > 0 ? `+${d.delta}` : d.delta})
                </div>
              ))}
            </div>
          ))}
        </div>
      </details>
    </Card>
  )
}
