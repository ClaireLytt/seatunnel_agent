import { type ReactNode, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Card } from '@shared/components/card'

// Accordion in the uitest editor style: mono toggle line + sliding card.
export function Collapsible({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="font-mono text-sm text-ink-soft underline-offset-4 hover:underline"
      >
        {open ? '▾' : '▸'} {title}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <Card className="mt-2">{children}</Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
