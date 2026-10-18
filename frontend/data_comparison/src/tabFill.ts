import { useEffect } from 'react'

// Tab-fills-placeholder behavior (spec "Further Notes"): pressing Tab in an
// empty input/textarea fills in its placeholder. Reimplements the legacy
// text2sql resources/tab_fill.js the Gradio page injected, as a document-level
// hook. The native value setter + bubbled 'input' event make React's
// controlled inputs pick the value up.
export function useTabFill() {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return
      const el = e.target
      if (!(el instanceof HTMLInputElement) && !(el instanceof HTMLTextAreaElement)) return
      if (el.value.trim() !== '' || !el.placeholder) return
      e.preventDefault()
      const proto =
        el instanceof HTMLTextAreaElement
          ? HTMLTextAreaElement.prototype
          : HTMLInputElement.prototype
      Object.getOwnPropertyDescriptor(proto, 'value')?.set?.call(el, el.placeholder)
      el.dispatchEvent(new Event('input', { bubbles: true }))
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])
}
