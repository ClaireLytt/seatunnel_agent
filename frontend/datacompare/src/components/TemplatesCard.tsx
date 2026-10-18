import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  batchRunTemplates,
  deleteTemplate,
  listTemplates,
  loadTemplate,
  saveTemplate,
  type ComparisonTemplate,
  type TemplateSummary,
} from '@/api'
import { Collapsible, inputCls, labelCls, smallBtnCls } from '@/components/Collapsible'

// Comparison templates (legacy ui.py accordion D + F6): save the current
// tables + options under a name, load one back into the form, delete the
// selected one, and batch-run a multi-selection into one combined card.
export function TemplatesCard({
  sessionId,
  getTemplate,
  onApply,
  onResult,
}: {
  sessionId: string
  getTemplate: () => Omit<ComparisonTemplate, 'name'>
  onApply: (tmpl: ComparisonTemplate) => void
  onResult: (html: string) => void
}) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language.startsWith('zh') ? 'zh' : 'en'
  const [name, setName] = useState('')
  const [templates, setTemplates] = useState<TemplateSummary[]>([])
  const [selected, setSelected] = useState('')
  const [batchSelected, setBatchSelected] = useState<string[]>([])
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)

  const fail = (e: unknown) => setStatus(`❌ ${e instanceof Error ? e.message : e}`)

  const refresh = () =>
    listTemplates()
      .then((ts) => {
        setTemplates(ts)
        setSelected('')
        setBatchSelected([])
      })
      .catch(fail)

  const onSave = async () => {
    if (!name.trim()) {
      setStatus(`❌ ${t('templateName')}`)
      return
    }
    try {
      await saveTemplate({ name: name.trim(), ...getTemplate() })
      setStatus(`✅ ${t('templateSaved')}`)
      await refresh()
    } catch (e) {
      fail(e)
    }
  }

  const onLoad = async () => {
    if (!selected) {
      setStatus(t('templateNoTemplates'))
      return
    }
    try {
      onApply(await loadTemplate(selected))
      setStatus(`✅ ${selected}`)
    } catch (e) {
      fail(e)
    }
  }

  const onDelete = async () => {
    if (!selected) {
      setStatus(t('templateNoTemplates'))
      return
    }
    try {
      await deleteTemplate(selected)
      setStatus(`✅ ${t('templateDeleted')}`)
      await refresh()
    } catch (e) {
      fail(e)
    }
  }

  const onBatchRun = async () => {
    setBusy(true)
    try {
      onResult(
        await batchRunTemplates({ session_id: sessionId, names: batchSelected, lang }),
      )
    } catch (e) {
      fail(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Collapsible title={t('templates')} onOpen={refresh} testId="templates-card">
      <label className={labelCls} htmlFor="template-name">
        {t('templateName')}
      </label>
      <input
        id="template-name"
        className={inputCls}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <button type="button" className={`${smallBtnCls} mt-2`} onClick={onSave}>
        {t('templateSave')}
      </button>

      <div className="mt-3">
        <label className={labelCls} htmlFor="template-load">
          {t('templateLoad')}
        </label>
        <select
          id="template-load"
          className={inputCls}
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          <option value=""></option>
          {templates.map((tmpl) => (
            <option key={tmpl.id} value={tmpl.name}>
              {tmpl.name}
            </option>
          ))}
        </select>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <button type="button" className={smallBtnCls} onClick={onLoad}>
          {t('templateLoad')}
        </button>
        <button type="button" className={smallBtnCls} onClick={onDelete} aria-label="delete">
          🗑
        </button>
      </div>
      {status && (
        <div
          data-testid="template-status"
          className="mt-2 truncate font-mono text-[12px]"
          style={{ color: status.startsWith('✅') ? 'var(--ok)' : 'var(--accent)' }}
          title={status}
        >
          {status}
        </div>
      )}

      <div className="mt-3">
        <label className={labelCls} htmlFor="batch-templates">
          {t('batchTemplates')}
        </label>
        <select
          id="batch-templates"
          multiple
          className={`${inputCls} min-h-[72px]`}
          value={batchSelected}
          onChange={(e) =>
            setBatchSelected(Array.from(e.target.selectedOptions, (o) => o.value))
          }
        >
          {templates.map((tmpl) => (
            <option key={tmpl.id} value={tmpl.name}>
              {tmpl.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          className={`${smallBtnCls} mt-2`}
          disabled={busy}
          onClick={onBatchRun}
        >
          {busy ? t('running') : t('batchTemplatesRun')}
        </button>
      </div>
    </Collapsible>
  )
}
