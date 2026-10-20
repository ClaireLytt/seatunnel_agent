export { fieldCls, labelCls, smallBtnCls } from '@shared/constants'

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
