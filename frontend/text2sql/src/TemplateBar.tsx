import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { langOf } from '@shared/lang'
import { fetchTemplates, type Template } from '@/api'

/** Quick-access template buttons above the chat input. */
export function TemplateBar({ onSelect }: { onSelect: (hint: string) => void }) {
  const { i18n } = useTranslation()
  const [templates, setTemplates] = useState<Template[]>([])

  useEffect(() => {
    fetchTemplates().then((r) => setTemplates(r.templates))
  }, [])

  if (templates.length === 0) return null

  const lang = langOf(i18n)

  return (
    <div className="st-template-bar flex flex-wrap gap-1.5 pb-2">
      {templates.map((t) => (
        <button
          key={t.id}
          onClick={() => {
            const name = lang === 'zh' ? t.name_zh : t.name_en
            const hint =
              lang === 'zh' ? `使用${name}模式分析 ` : `Use the ${name} pattern to analyze `
            onSelect(hint)
          }}
          title={lang === 'zh' ? t.description_zh : t.description_en}
          className="rounded border border-line px-2 py-0.5 font-mono text-[11px] text-muted transition hover:border-ink hover:text-ink"
        >
          {lang === 'zh' ? t.name_zh : t.name_en}
        </button>
      ))}
    </div>
  )
}
