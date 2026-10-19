import { useMemo } from 'react'
import { marked } from 'marked'

// Format reports are generated server-side (report.render_markdown /
// render_batch_markdown) — trusted markdown, rendered with marked
// (config_lint ReportView precedent).
export function ReportView({ markdown }: { markdown: string }) {
  const html = useMemo(() => marked.parse(markdown, { async: false }), [markdown])
  return <div className="sf-report" dangerouslySetInnerHTML={{ __html: html }} />
}
