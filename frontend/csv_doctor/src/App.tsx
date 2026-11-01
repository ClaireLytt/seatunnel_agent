import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runDiagnose, type DiagnoseResponse } from '@/api'

// the two garbled names are 订单一 / 订单二 read as latin-1 (escaped so
// no raw C1 control characters live in this source file)
const MOJI_1 = 'è®¢å\u008d\u0095ä¸\u0080'
const MOJI_2 = 'è®¢å\u008d\u0095äº\u008c'
const DEMO_DATA = `id;name;amount;name
1;${MOJI_1};10.5;x
2;b;20
3;${MOJI_2};30;y;extra
4;bad;40;z`

export default function App() {
  const { t, i18n } = useTranslation()
  const [data, setData] = useState(DEMO_DATA)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((q: string, lang: string, useLlm: boolean) =>
    runDiagnose(q, lang, useLlm),
  )

  const run = () => {
    if (!data.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(data, i18n.language, llm)
  }

  const clear = () => {
    setData(DEMO_DATA)
    runner.reset()
  }

  const result = runner.result as DiagnoseResponse | null
  const fixed = (result?.result?.fixed_csv as string | undefined) ?? ''

  const download = () => {
    const blob = new Blob([fixed], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'fixed.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / csvdoctor" maxW="max-w-[620px]" />

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
            {fixed && (
              <button
                onClick={download}
                className="mt-2 w-full rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
              >
                {t('download_btn')}
              </button>
            )}
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
