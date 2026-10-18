import { useMemo } from 'react'
import { marked } from 'marked'

// Lint reports are generated server-side (report.render_markdown /
// render_batch_markdown) — trusted markdown, rendered with marked
// (config_migrate ReportView precedent).
export function ReportView({ markdown }: { markdown: string }) {
  const html = useMemo(() => marked.parse(markdown, { async: false }), [markdown])
  return <div className="cl-report" dangerouslySetInnerHTML={{ __html: html }} />
}
