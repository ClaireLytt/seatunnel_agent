import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runProfile, type ProfileResponse } from '@/api'

const DEMO_DATA = `order_id,user_id,amount,status,created_at,email
1001,u001,129.90,paid,2026-10-01,alice@example.com
1002,u002,59.00,paid,2026-10-01,bob@example.com
1003,u003,"1,299.00",paid,2026-10-02,carol@example.com
1004,u004,23.50,PAID,2026-10-02,dave@example
1005,u005,88.00,paid,10/03/2026,erin@example.com
1006,u006,15.00,paid ,2026-10-03,frank@example.com
1007,u007,,paid,2026-10-04,grace@example.com`

export default function App() {
  const { t, i18n } = useTranslation()
  const [data, setData] = useState(DEMO_DATA)
  const [dataFile, setDataFile] = useState('')
  const [maxRows, setMaxRows] = useState('2000')
  const [llm, setLlm] = useState(false)
  const runner = useRunner(
    (file: string | null, text: string, cap: number, lang: string, useLlm: boolean) =>
      runProfile(file, text, cap, lang, useLlm),
  )

  const run = () => {
    if (!dataFile.trim() && !data.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(
      dataFile.trim() || null,
      dataFile.trim() ? '' : data,
      Math.max(1, parseInt(maxRows, 10) || 2000),
      i18n.language,
      llm,
    )
  }

  const clear = () => {
    setData(DEMO_DATA)
    setDataFile('')
    setMaxRows('2000')
    runner.reset()
  }

  const result = runner.result as ProfileResponse | null
  const error =
    runner.error && (runner.error.includes('bad_dir') ? t('bad_dir') + runner.error : runner.error)

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / sampleprofile" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[420px]">
          <Card>
            <label className="mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('data_label')}
            </label>
            <textarea
              value={data}
              onChange={(e) => setData(e.target.value)}
              placeholder={t('data_ph')}
              rows={12}
              spellCheck={false}
              className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className="mb-2 mt-3 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('file_label')}
            </label>
            <input
              value={dataFile}
              onChange={(e) => setDataFile(e.target.value)}
              placeholder={t('file_ph')}
              spellCheck={false}
              className="w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink"
            />
            <label className="mb-2 mt-3 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('maxrows_label')}
            </label>
            <input
              value={maxRows}
              onChange={(e) => setMaxRows(e.target.value.replace(/[^\d]/g, ''))}
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
            {error && (
              <div className="mb-3 font-mono text-sm" style={{ color: 'var(--accent)' }}>
                {error}
              </div>
            )}
            {result?.report && <ReportView markdown={result.report} />}
            {!result?.report && !error && <p className="text-sm text-muted">{t('report_ph')}</p>}
          </Card>
        </main>
      </div>
    </div>
  )
}
