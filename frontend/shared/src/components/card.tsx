import { type ReactNode } from 'react'
import { cn } from '../utils'

// Static panel card: bordered, with the engineering-paper top rule.
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
