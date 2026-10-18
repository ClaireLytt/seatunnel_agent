// Shared class strings + client-side download helper for the page panels.

export const fieldCls =
  'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'
export const labelCls =
  'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
export const smallBtnCls =
  'rounded border-[1.5px] border-ink px-3 py-1.5 font-mono text-xs font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50'

/** Client-side file download (replaces the Gradio DownloadButtons). */
export function downloadText(name: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}
