import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runGenerate, type GenResponse } from '@/api'

const DEMO_DATA = `order_id,status,amount,city,note
1,paid,10.5,bj,
2,paid,20.0,sh,x
3,refund,15.0,bj,
4,paid,8.0,gz,
5,paid,33.2,sh,
6,refund,7.7,bj,y
7,paid,18.4,gz,
8,paid,25.1,sh,`

export default function App() {
  const { t, i18n } = useTranslation()
  const [data, setData] = useState(DEMO_DATA)
  const [table, setTable] = useState('dwd.orders')
  const [where, setWhere] = useState("dt = '${yesterday_pt}'")
  const [llm, setLlm] = useState(false)
  const runner = useRunner((q: string, tbl: string, w: string, lang: string, useLlm: boolean) =>
    runGenerate(q, tbl, w, lang, useLlm),
  )

  const run = () => {
    if (!data.trim() || !table.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(data, table.trim(), where, i18n.language, llm)
  }

  const clear = () => {
    setData(DEMO_DATA)
    setTable('dwd.orders')
    setWhere("dt = '${yesterday_pt}'")
    runner.reset()
  }

  const result = runner.result as GenResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const input =
    'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / dqrulegen" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[440px]">
          <Card>
            <label className={label}>{t('data_label')}</label>
            <textarea
              value={data}
              onChange={(e) => setData(e.target.value)}
              placeholder={t('data_ph')}
              rows={11}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className={`${label} mt-3`}>{t('table_label')}</label>
            <input
              value={table}
              onChange={(e) => setTable(e.target.value)}
              placeholder={t('table_ph')}
              spellCheck={false}
              className={input}
            />
            <label className={`${label} mt-3`}>{t('where_label')}</label>
            <input
              value={where}
              onChange={(e) => setWhere(e.target.value)}
              placeholder={t('where_ph')}
              spellCheck={false}
              className={input}
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
