import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runPreview, type PreviewResponse } from '@/api'

const DEMO_DATA = `user_id,user_name,mobile,id_card,email,city,amount
1001,王小明,13812340001,110101199003071234,xiaoming@example.com,北京,120.50
1002,李雷,13998760002,310101198811021345,leilei@test.org,上海,88.00
1003,韩梅梅,15612340003,440101199512153456,meimei@demo.cn,广州,230.10
1004,赵强,18712340004,120101198701314567,qiang.zhao@corp.com,天津,45.90`

export default function App() {
  const { t, i18n } = useTranslation()
  const [data, setData] = useState(DEMO_DATA)
  const [previewRows, setPreviewRows] = useState('20')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((q: string, n: number, lang: string, useLlm: boolean) =>
    runPreview(q, n, lang, useLlm),
  )

  const run = () => {
    if (!data.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    const n = Math.max(1, parseInt(previewRows, 10) || 20)
    void runner.run(data, n, i18n.language, llm)
  }

  const clear = () => {
    setData(DEMO_DATA)
    setPreviewRows('20')
    runner.reset()
  }

  const result = runner.result as PreviewResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / maskpreview" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[440px]">
          <Card>
            <label className={label}>{t('data_label')}</label>
            <textarea
              value={data}
              onChange={(e) => setData(e.target.value)}
              placeholder={t('data_ph')}
              rows={12}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className={`${label} mt-3`}>{t('rows_label')}</label>
            <input
              value={previewRows}
              onChange={(e) => setPreviewRows(e.target.value)}
              inputMode="numeric"
              spellCheck={false}
              className="w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className="mt-3 flex cursor-pointer items-center gap-2 font-mono text-[12px] text-ink-soft">
              <input type="checkbox" checked={llm} onChange={(e) => setLlm(e.target.checked)} />
              {t('llm_label')}
            </label>
            <button
              onClick={run}
              disabled={runner.busy}
              className="mt-3 w-full rounded border-[1.5px] border-ink bg-ink px-4 py-2 font-mono text-sm font-semibold text-[var(--paper)] transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50"
            >
              {runner.busy ? t('running') : t('run_btn')}
            </button>
            <button
              onClick={clear}
              disabled={runner.busy}
              className="mt-2 w-full rounded border-[1.5px] border-transparent px-4 py-2 font-mono text-sm text-ink-soft transition hover:border-line disabled:opacity-50"
            >
              {t('clear_btn')}
            </button>
          </Card>
        </aside>

        <main className="min-w-0 flex-1">
          <Card>
            {runner.error && (
              <div className="mb-3 font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {runner.error}
              </div>
            )}
            {result?.report && <ReportView markdown={result.report} />}
            {!result?.report && !runner.error && (
              <p className="text-sm text-muted">{t('report_ph')}</p>
            )}
          </Card>
        </main>
      </div>
    </div>
  )
}
