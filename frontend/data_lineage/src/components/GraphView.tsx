import { useEffect, useRef } from 'react'
import mermaid from 'mermaid'

let seq = 0

/** Mermaid lineage graph; clicking a node reports its table name (legacy
 * iframe node-jump bridge, now a plain callback). */
export function GraphView({ source, onNode }: { source: string; onNode: (table: string) => void }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el || !source.trim()) return
    let cancelled = false
    const dark = document.documentElement.getAttribute('data-theme') === 'dark'
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'loose',
      theme: dark ? 'dark' : 'default',
    })
    mermaid
      .render(`lin-graph-${++seq}`, source)
      .then(({ svg }) => {
        if (cancelled || !ref.current) return
        ref.current.innerHTML = svg
        ref.current.querySelectorAll<SVGGElement>('.node').forEach((n) => {
          n.style.cursor = 'pointer'
          n.addEventListener('click', () => {
            const m = (n.textContent || '').trim().match(/^[A-Za-z0-9_.$-]+/)
            if (m) onNode(m[0])
          })
        })
      })
      .catch(() => {
        if (!cancelled && ref.current) ref.current.textContent = source
      })
    return () => {
      cancelled = true
    }
  }, [source, onNode])

  if (!source.trim()) return null
  return (
    <div
      ref={ref}
      className="overflow-x-auto rounded border border-line bg-[var(--paper)] p-2 text-center"
    />
  )
}
