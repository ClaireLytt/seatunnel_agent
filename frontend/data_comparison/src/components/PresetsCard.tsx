import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  deletePreset,
  listPresets,
  loadPreset,
  savePreset,
  type PresetConnection,
  type PresetSummary,
} from '@/api'
import { Collapsible, inputCls, labelCls, smallBtnCls } from '@/components/Collapsible'

// Connection presets (legacy ui.py:1735-1752): save the current connect
// form of side A or B under name + environment, auto-apply on select,
// delete the preset selected in the A dropdown.
export function PresetsCard({
  getFields,
  onApply,
  resetSeq,
}: {
  getFields: (side: 'a' | 'b') => Omit<PresetConnection, 'environment'>
  onApply: (side: 'a' | 'b', preset: PresetConnection) => void
  resetSeq: number
}) {
  const { t } = useTranslation()
  const [name, setName] = useState('')
  const [env, setEnv] = useState('')
  const [presets, setPresets] = useState<PresetSummary[]>([])
  const [selA, setSelA] = useState('')
  const [selB, setSelB] = useState('')
  const [status, setStatus] = useState('')

  // options reset also clears the preset name/env inputs (legacy 27-output reset)
  useEffect(() => {
    if (resetSeq > 0) {
      setName('')
      setEnv('')
    }
  }, [resetSeq])

  const refresh = () =>
    listPresets()
      .then((ps) => {
        setPresets(ps)
        setSelA('')
        setSelB('')
      })
      .catch((e) => setStatus(`❌ ${e instanceof Error ? e.message : e}`))

  const onSave = async (side: 'a' | 'b') => {
    if (!name.trim()) {
      setStatus(`❌ ${t('presetName')}`)
      return
    }
    try {
      await savePreset({ name: name.trim(), ...getFields(side), environment: env.trim() })
      setStatus(`✅ ${t('presetSaved')}: ${name.trim()}`)
      await refresh()
    } catch (e) {
      setStatus(`❌ ${e instanceof Error ? e.message : e}`)
    }
  }

  const onSelect = async (side: 'a' | 'b', value: string) => {
    ;(side === 'a' ? setSelA : setSelB)(value)
    if (!value) return
    try {
      onApply(side, await loadPreset(value))
    } catch (e) {
      setStatus(`❌ ${e instanceof Error ? e.message : e}`)
    }
  }

  const onDelete = async () => {
    if (!selA) {
      setStatus(t('presetNoPresets'))
      return
    }
    try {
      await deletePreset(selA)
      setStatus(`✅ ${t('presetDeleted')}`)
      await refresh()
    } catch (e) {
      setStatus(`❌ ${e instanceof Error ? e.message : e}`)
    }
  }

  const optionLabel = (p: PresetSummary) =>
    p.environment ? `${p.name} (${p.environment})` : p.name

  return (
    <Collapsible title={t('presets')} onOpen={refresh} testId="presets-card">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls} htmlFor="preset-name">
            {t('presetName')}
          </label>
          <input
            id="preset-name"
            className={inputCls}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label className={labelCls} htmlFor="preset-env">
            {t('presetEnv')}
          </label>
          <input
            id="preset-env"
            className={inputCls}
            value={env}
            onChange={(e) => setEnv(e.target.value)}
          />
        </div>
      </div>

      <div className="mt-3 flex gap-2">
        <button type="button" className={smallBtnCls} onClick={() => onSave('a')}>
          {t('presetSave')} (A)
        </button>
        <button type="button" className={smallBtnCls} onClick={() => onSave('b')}>
          {t('presetSave')} (B)
        </button>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        {(['a', 'b'] as const).map((side) => (
          <div key={side}>
            <label className={labelCls} htmlFor={`preset-load-${side}`}>
              {t('presetLoad')} ({side.toUpperCase()})
            </label>
            <select
              id={`preset-load-${side}`}
              className={inputCls}
              value={side === 'a' ? selA : selB}
              onChange={(e) => onSelect(side, e.target.value)}
            >
              <option value=""></option>
              {presets.map((p) => (
                <option key={p.id} value={p.name}>
                  {optionLabel(p)}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-3">
        <button type="button" className={smallBtnCls} onClick={onDelete} aria-label={t('delete')}>
          🗑
        </button>
        {status && (
          <span
            data-testid="preset-status"
            className="min-w-0 flex-1 truncate font-mono text-[12px]"
            style={{ color: status.startsWith('✅') ? 'var(--ok)' : 'var(--accent)' }}
            title={status}
          >
            {status}
          </span>
        )}
      </div>
    </Collapsible>
  )
}
