import { useEffect, useRef } from 'react'
import mermaid from 'mermaid'

let seq = 0

/** Severity-coloured impact graph (mermaid npm; data_lineage GraphView
 * precedent minus node clicks — the impact graph has no jump semantics). */
export function GraphView({ source }: { source: string }) {
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
      .render(`imp-graph-${++seq}`, source)
      .then(({ svg }) => {
        if (!cancelled && ref.current) ref.current.innerHTML = svg
      })
      .catch(() => {
        if (!cancelled && ref.current) ref.current.textContent = source
      })
    return () => {
      cancelled = true
    }
  }, [source])

  if (!source.trim()) return null
  return (
    <div
      ref={ref}
      className="overflow-x-auto rounded border border-line bg-[var(--paper)] p-2 text-center"
    />
  )
}
