import { useMotionValue, motion, useMotionTemplate } from 'motion/react'
import { type ReactNode, type MouseEvent } from 'react'
import { cn } from '@/lib/utils'

// Adapted from Aceternity UI "Card Spotlight" — recolored to the
// engineering-paper theme (ink grid highlight, no blue-purple gradients).
export function SpotlightCard({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)
  const onMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    const { left, top } = e.currentTarget.getBoundingClientRect()
    mouseX.set(e.clientX - left)
    mouseY.set(e.clientY - top)
  }
  return (
    <div
      onMouseMove={onMouseMove}
      className={cn(
        'group relative rounded border border-line border-t-[3px] border-t-ink bg-card p-5',
        className,
      )}
    >
      <motion.div
        className="pointer-events-none absolute inset-0 rounded opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background: useMotionTemplate`radial-gradient(260px circle at ${mouseX}px ${mouseY}px, var(--grid-bold), transparent 70%)`,
        }}
      />
      <div className="relative">{children}</div>
    </div>
  )
}
