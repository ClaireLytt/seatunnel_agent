import { useMemo } from 'react'
import { marked } from 'marked'

/**
 * Renders a Markdown report as sanitized HTML.
 *
 * @param markdown  - raw Markdown string
 * @param className - wrapper div class (each workspace styles its own report)
 * @param onLineClick - optional callback when a `#srline-N` anchor is clicked
 */
export function ReportView({
  markdown,
  className,
  onLineClick,
}: {
  markdown: string
  className?: string
  onLineClick?: (line: number) => void
}) {
  const html = useMemo(() => marked.parse(markdown, { async: false }), [markdown])
  const onClick = onLineClick
    ? (e: React.MouseEvent<HTMLDivElement>) => {
        const a = (e.target as HTMLElement).closest('a[href*="#srline-"]')
        if (!a) return
        e.preventDefault()
        const line = parseInt(a.getAttribute('href')!.split('#srline-')[1], 10)
        if (line) onLineClick(line)
      }
    : undefined
  return (
    <div
      className={className}
      onClick={onClick}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
