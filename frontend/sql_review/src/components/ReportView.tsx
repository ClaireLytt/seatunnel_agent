import { useMemo } from 'react'
import { marked } from 'marked'

// Review reports are generated server-side (report.render_report) — trusted
// markdown, rendered with marked. Tables and #srline-N anchors are styled
// via the .sr-report rules in index.css.
export function ReportView({
  markdown,
  onLineClick,
}: {
  markdown: string
  onLineClick?: (line: number) => void
}) {
  const html = useMemo(() => marked.parse(markdown, { async: false }), [markdown])

  // finding locations render as [行 N](#srline-N); clicking jumps to the line
  const onClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const a = (e.target as HTMLElement).closest('a[href*="#srline-"]')
    if (!a) return
    e.preventDefault()
    const line = parseInt(a.getAttribute('href')!.split('#srline-')[1], 10)
    if (line && onLineClick) onLineClick(line)
  }

  return (
    <div className="sr-report" onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} />
  )
}
