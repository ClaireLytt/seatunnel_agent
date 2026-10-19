import { useMemo } from 'react'
import { marked } from 'marked'

// Migration reports are generated server-side (report.render_migrate_markdown)
// — trusted markdown, rendered with marked (sql_review ReportView precedent).
export function ReportView({ markdown }: { markdown: string }) {
  const html = useMemo(() => marked.parse(markdown, { async: false }), [markdown])
  return <div className="cm-report" dangerouslySetInnerHTML={{ __html: html }} />
}
