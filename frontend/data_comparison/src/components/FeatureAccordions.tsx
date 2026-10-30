import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { featureAction, type CompareOptions, type FeatureAction, type FeatureFields } from '@/api'
import { Collapsible, inputCls, labelCls, smallBtnCls } from '@/components/Collapsible'

// The seven legacy analysis accordions (ticket 06), 1:1 with the Gradio
// sidebar: incremental watermark, quality rules, skew, checksum (incl.
// chunked verify), partition, custom aggregates, custom SQL A/B. Each
// action posts the global options plus its own fields and renders the
// server-built card into the shared results container.
export function FeatureAccordions({
  sessionId,
  tableA,
  tableB,
  options,
  onResult,
  resetSeq,
  onFields,
  apply,
}: {
  sessionId: string
  tableA: string
  tableB: string
  options: CompareOptions
  onResult: (html: string) => void
  resetSeq: number
  // reports the optional compare-all stage fields + the template fields up
  onFields?: (f: FeatureFields) => void
  // writes template fields back into the accordions (applyPreset mechanism)
  apply?: { seq: number; fields: FeatureFields }
}) {
  const { t, i18n } = useTranslation()
  const [busy, setBusy] = useState<string | null>(null)

  // Per-accordion fields (reset by the global options reset, like legacy)
  const [watermarkCol, setWatermarkCol] = useState('')
  const [watermarkVal, setWatermarkVal] = useState('')
  const [qualityRules, setQualityRules] = useState('')
  const [skewCols, setSkewCols] = useState('')
  const [checksumCols, setChecksumCols] = useState('')
  const [partitionCol, setPartitionCol] = useState('')
  const [customAgg, setCustomAgg] = useState('')
  const [sqlA, setSqlA] = useState('')
  const [sqlB, setSqlB] = useState('')

  useEffect(() => {
    onFields?.({
      skew_columns: skewCols,
      checksum_columns: checksumCols,
      partition_col: partitionCol,
      expressions: customAgg,
      // template snapshot fields (TemplatesCard save reads these live)
      watermark_col: watermarkCol,
      quality_rules: qualityRules,
    })
  }, [skewCols, checksumCols, partitionCol, customAgg, watermarkCol, qualityRules, onFields])

  // applyTemplate writes watermark/quality back into the accordions
  useEffect(() => {
    if (!apply) return
    setWatermarkCol(apply.fields.watermark_col ?? '')
    setQualityRules(apply.fields.quality_rules ?? '')
  }, [apply])

  useEffect(() => {
    if (resetSeq === 0) return
    setWatermarkCol('')
    setWatermarkVal('')
    setQualityRules('')
    setSkewCols('')
    setChecksumCols('')
    setPartitionCol('')
    setCustomAgg('')
    setSqlA('')
    setSqlB('')
  }, [resetSeq])

  const run = async (action: FeatureAction, fields: FeatureFields, busyKey?: string) => {
    const key = busyKey ?? action
    setBusy(key)
    try {
      const html = await featureAction(action, {
        session_id: sessionId,
        table_a: tableA,
        table_b: tableB,
        lang: i18n.language.startsWith('zh') ? 'zh' : 'en',
        ...options,
        ...fields,
      })
      onResult(html)
    } catch (e) {
      onResult(
        `<div style="color:var(--accent);font-family:monospace;font-size:13px;">❌ ${
          e instanceof Error ? e.message : String(e)
        }</div>`,
      )
    } finally {
      setBusy(null)
    }
  }

  const runBtn = (label: string, key: string, onClick: () => void) => (
    <button
      type="button"
      data-testid={`feature-${key}`}
      onClick={onClick}
      disabled={!sessionId || busy !== null}
      className={smallBtnCls}
    >
      {busy === key ? t('running') : label}
    </button>
  )

  const field = (label: string, value: string, set: (v: string) => void, hint = '') => (
    <div>
      <label className={labelCls}>{label}</label>
      <input
        className={inputCls}
        value={value}
        placeholder={hint}
        onChange={(e) => set(e.target.value)}
      />
    </div>
  )

  return (
    <div className="flex flex-col gap-2" data-testid="feature-accordions">
      <Collapsible title={t('incremental')} testId="accordion-incremental">
        <div className="flex flex-col gap-2">
          {field(t('watermarkCol'), watermarkCol, setWatermarkCol, t('watermarkColHint'))}
          {field(t('watermarkVal'), watermarkVal, setWatermarkVal, '2024-01-01 00:00:00')}
          {runBtn(t('incrementalRun'), 'incremental', () =>
            run('incremental', { watermark_col: watermarkCol, watermark_val: watermarkVal }),
          )}
        </div>
      </Collapsible>

      <Collapsible title={t('quality')} testId="accordion-quality">
        <div className="flex flex-col gap-2">
          {field(t('qualityRules'), qualityRules, setQualityRules, t('qualityRulesHint'))}
          {runBtn(t('qualityRun'), 'quality', () =>
            run('quality', { quality_rules: qualityRules }),
          )}
        </div>
      </Collapsible>

      <Collapsible title={t('skew')} testId="accordion-skew">
        <div className="flex flex-col gap-2">
          {field(t('skewCols'), skewCols, setSkewCols, t('skewColsHint'))}
          {runBtn(t('skewRun'), 'skew', () => run('skew', { skew_columns: skewCols }))}
        </div>
      </Collapsible>

      <Collapsible title={t('checksum')} testId="accordion-checksum">
        <div className="flex flex-col gap-2">
          {field(t('checksum'), checksumCols, setChecksumCols, t('checksumColsHint'))}
          {runBtn(t('checksumRun'), 'checksum', () =>
            run('checksum', { checksum_columns: checksumCols }),
          )}
          {/* chunked verification (uses Key Columns as the numeric PK) */}
          {runBtn(t('chunkedRun'), 'chunked', () =>
            run('chunked', { checksum_columns: checksumCols }),
          )}
        </div>
      </Collapsible>

      <Collapsible title={t('partition')} testId="accordion-partition">
        <div className="flex flex-col gap-2">
          {field(t('partitionCol'), partitionCol, setPartitionCol, t('partitionColHint'))}
          {runBtn(t('partitionRun'), 'partition', () =>
            run('partition', { partition_col: partitionCol }),
          )}
        </div>
      </Collapsible>

      <Collapsible title={t('customAgg')} testId="accordion-custom-agg">
        <div className="flex flex-col gap-2">
          <div>
            <label className={labelCls}>{t('customAgg')}</label>
            <textarea
              className={inputCls}
              rows={3}
              value={customAgg}
              placeholder={t('customAggHint')}
              onChange={(e) => setCustomAgg(e.target.value)}
            />
          </div>
          {runBtn(t('customAggRun'), 'custom-agg', () =>
            run('custom-agg', { expressions: customAgg }),
          )}
        </div>
      </Collapsible>

      <Collapsible title={t('customSql')} testId="accordion-sql">
        <div className="flex flex-col gap-2">
          <div>
            <label className={labelCls}>SQL (A)</label>
            <textarea
              className={inputCls}
              rows={3}
              value={sqlA}
              placeholder={t('sqlPlaceholder')}
              onChange={(e) => setSqlA(e.target.value)}
            />
          </div>
          <div>
            <label className={labelCls}>SQL (B)</label>
            <textarea
              className={inputCls}
              rows={3}
              value={sqlB}
              placeholder={t('sqlPlaceholder')}
              onChange={(e) => setSqlB(e.target.value)}
            />
          </div>
          {runBtn(t('sqlRun'), 'sql', () => run('sql', { sql_a: sqlA, sql_b: sqlB }))}
        </div>
      </Collapsible>
    </div>
  )
}
