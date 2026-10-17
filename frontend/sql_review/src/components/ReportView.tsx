import { useMemo } from 'react'
import { marked } from 'marked'

// Review reports are generated server-side (report.render_report) — trusted
// markdown, rendered with marked. Tables and #srline-N anchors are styled
// via the .sr-report rules in index.css.
export function ReportView({ markdown }: { markdown: string }) {
  const html = useMemo(() => marked.parse(markdown, { async: false }), [markdown])
  return <div className="sr-report" dangerouslySetInnerHTML={{ __html: html }} />
}
