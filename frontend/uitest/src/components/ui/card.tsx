import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

// Static panel card: bordered, with the engineering-paper top rule.
// (The former mouse-following spotlight effect was removed by request.)
export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'rounded border border-line border-t-[3px] border-t-ink bg-card p-5',
        className,
      )}
    >
      {children}
    </div>
  )
}
