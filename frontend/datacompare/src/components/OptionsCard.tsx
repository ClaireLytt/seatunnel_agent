import { useTranslation } from 'react-i18next'
import { type CompareOptions } from '@/api'
import { Collapsible, inputCls, labelCls, smallBtnCls } from '@/components/Collapsible'

// Global options block (legacy ui.py:1810-1849): WHERE, threshold, key
// columns, column mapping, sampling strategy (stratified column only when
// STRATIFIED), masking, one-click reset. Pure frontend state — the values
// ride on every comparison action request.
export function OptionsCard({
  strategies,
  options,
  onChange,
  onReset,
}: {
  strategies: string[]
  options: CompareOptions
  onChange: (next: CompareOptions) => void
  onReset: () => void
}) {
  const { t } = useTranslation()
  const set = (patch: Partial<CompareOptions>) => onChange({ ...options, ...patch })

  return (
    <Collapsible title={t('options')} defaultOpen testId="options-card">
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className={labelCls} htmlFor="opt-where">
            {t('where')}
          </label>
          <input
            id="opt-where"
            className={inputCls}
            value={options.where}
            onChange={(e) => set({ where: e.target.value })}
            placeholder={t('whereHint')}
          />
        </div>

        <div>
          <label className={labelCls} htmlFor="opt-threshold">
            {t('threshold')}
          </label>
          <input
            id="opt-threshold"
            className={inputCls}
            value={options.threshold}
            onChange={(e) => set({ threshold: e.target.value })}
            placeholder={t('thresholdHint')}
          />
        </div>

        <div>
          <label className={labelCls} htmlFor="opt-keys">
            {t('keyColumns')}
          </label>
          <input
            id="opt-keys"
            className={inputCls}
            value={options.key_columns}
            onChange={(e) => set({ key_columns: e.target.value })}
            placeholder="id, order_id"
          />
        </div>

        <div className="col-span-2">
          <label className={labelCls} htmlFor="opt-mapping">
            {t('colMapping')}
          </label>
          <input
            id="opt-mapping"
            className={inputCls}
            value={options.column_mapping}
            onChange={(e) => set({ column_mapping: e.target.value })}
            placeholder={t('colMappingHint')}
          />
        </div>

        <div>
          <label className={labelCls} htmlFor="opt-strategy">
            {t('sampleStrategy')}
          </label>
          <select
            id="opt-strategy"
            className={inputCls}
            value={options.sample_strategy}
            onChange={(e) =>
              set({
                sample_strategy: e.target.value,
                // legacy hides AND ignores the column outside STRATIFIED
                ...(e.target.value !== 'STRATIFIED' ? { stratified_col: '' } : {}),
              })
            }
          >
            {strategies.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {options.sample_strategy === 'STRATIFIED' && (
          <div>
            <label className={labelCls} htmlFor="opt-stratified">
              {t('stratifiedCol')}
            </label>
            <input
              id="opt-stratified"
              className={inputCls}
              value={options.stratified_col}
              onChange={(e) => set({ stratified_col: e.target.value })}
              placeholder={t('stratifiedColHint')}
            />
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <label className="flex items-center gap-2 font-mono text-[13px] text-fg">
          <input
            id="opt-masking"
            type="checkbox"
            checked={options.masking}
            onChange={(e) => set({ masking: e.target.checked })}
          />
          {t('masking')}
        </label>
        <button type="button" onClick={onReset} className={smallBtnCls}>
          {t('resetOptions')}
        </button>
      </div>
    </Collapsible>
  )
}
