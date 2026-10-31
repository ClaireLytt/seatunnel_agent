import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runGrade, type GradeResponse } from '@/api'

const DEMO_INVENTORY = `table,size_gb,access_cnt_30d,last_access,downstream_cnt
dws.orders_daily,120,860,2026-10-30,9
dwd.orders,900,420,2026-10-30,6
dim.users,15,510,2026-10-29,12
ods.orders_raw,1400,35,2026-10-30,1
tmp.backfill_201902,2300,0,2026-02-11,0
bak.orders_v1,1800,1,2026-05-02,0
ads.board_kpi,8,300,2026-10-30,0`

export default function App() {
  const { t, i18n } = useTranslation()
  const [inventory, setInventory] = useState(DEMO_INVENTORY)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((text: string, lang: string, useLlm: boolean) =>
    runGrade(text, lang, useLlm),
  )

  const run = () => {
    if (!inventory.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(inventory, i18n.language, llm)
  }

  const clear = () => {
    setInventory(DEMO_INVENTORY)
    runner.reset()
  }

  const result = runner.result as GradeResponse | null

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / assetvalue" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('inventory_label')}
            </label>
            <textarea
              value={inventory}
              onChange={(e) => setInventory(e.target.value)}
              placeholder={t('inventory_ph')}
              rows={14}
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
