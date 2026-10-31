import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runDiff, type DiffResponse } from '@/api'

const DEMO_LEFT = `env {
  parallelism = 2
  job.mode = "BATCH"
}
source {
  Jdbc {
    url = "jdbc:mysql://dev-db:3306/orders"
    password = "dev-secret"
  }
}
sink {
  Doris { table = "ods_orders_dev", batch_size = 100 }
}`

const DEMO_RIGHT = `env {
  parallelism = 8
  job.mode = "BATCH"
  checkpoint.interval = 60000
}
source {
  Jdbc {
    url = "jdbc:mysql://prod-db:3306/orders"
    password = "prod-secret"
    fetch_size = 500
  }
}
sink {
  Doris { table = "ods_orders" }
}`

export default function App() {
  const { t, i18n } = useTranslation()
  const [left, setLeft] = useState(DEMO_LEFT)
  const [right, setRight] = useState(DEMO_RIGHT)
  const [llm, setLlm] = useState(false)
  const runner = useRunner((a: string, b: string, lang: string, useLlm: boolean) =>
    runDiff(a, b, lang, useLlm),
  )

  const run = () => {
    if (!left.trim() || !right.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(left, right, i18n.language, llm)
  }

  const clear = () => {
    setLeft(DEMO_LEFT)
    setRight(DEMO_RIGHT)
    runner.reset()
  }

  const result = runner.result as DiffResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const area =
    'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / configdiff" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className={label}>{t('left_label')}</label>
            <textarea
              value={left}
              onChange={(e) => setLeft(e.target.value)}
              placeholder={t('config_ph')}
              rows={9}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('right_label')}</label>
            <textarea
              value={right}
              onChange={(e) => setRight(e.target.value)}
              placeholder={t('config_ph')}
              rows={9}
              spellCheck={false}
              className={area}
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
