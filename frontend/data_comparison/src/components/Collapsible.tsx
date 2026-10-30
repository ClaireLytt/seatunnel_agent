import { type ReactNode, useState } from 'react'
import { Card } from '@shared/components/card'

// Accordion in the sql_review Collapsible style: mono toggle line + card.
export function Collapsible({
  title,
  children,
  defaultOpen = false,
  onOpen,
  testId,
}: {
  title: string
  children: ReactNode
  defaultOpen?: boolean
  onOpen?: () => void
  testId?: string
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div data-testid={testId}>
      <button
        type="button"
        onClick={() => {
          if (!open) onOpen?.()
          setOpen((o) => !o)
        }}
        className="font-mono text-sm text-ink-soft underline-offset-4 hover:underline"
      >
        {open ? '▾' : '▸'} {title}
      </button>
      {open && <Card className="mt-2">{children}</Card>}
    </div>
  )
}

export const inputCls =
  'w-full rounded border border-line bg-card px-2.5 py-1.5 font-mono text-[13px] text-fg ' +
  'outline-none focus:border-ink'

export const labelCls = 'mb-1 block font-mono text-[10px] uppercase tracking-[0.16em] text-ink-soft'

export const smallBtnCls =
  'rounded border-[1.5px] border-ink px-3 py-1.5 font-mono text-[12px] text-ink transition ' +
  'enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard ' +
  'disabled:opacity-50'
