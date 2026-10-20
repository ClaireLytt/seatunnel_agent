import { useMemo } from 'react'
import { marked } from 'marked'

// Reports are generated server-side (report.render_markdown) — trusted markdown, rendered with marked
// (config_lint ReportView precedent).
export function ReportView({ markdown }: { markdown: string }) {
  const html = useMemo(() => marked.parse(markdown, { async: false }), [markdown])
  return <div className="md-report" dangerouslySetInnerHTML={{ __html: html }} />
}
