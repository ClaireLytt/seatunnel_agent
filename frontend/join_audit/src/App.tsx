import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { ReportView } from '@shared/components/ReportView'
import { useRunner } from '@shared/useRunner'
import { runAudit, type AuditResponse } from '@/api'

const DEMO_LEFT = `order_id,user_id,amount
1,101,10.5
2,101,20.0
3,102,15.0
4,103,8.0
5,104,30.0
6,,12.0
7,101,5.5
8,105,40.0`

const DEMO_RIGHT = `uid,tag
101,vip
101,new
102,vip
103,normal
108,vip
109,normal`

export default function App() {
  const { t, i18n } = useTranslation()
  const [left, setLeft] = useState(DEMO_LEFT)
  const [right, setRight] = useState(DEMO_RIGHT)
  const [keys, setKeys] = useState('user_id=uid')
  const [llm, setLlm] = useState(false)
  const runner = useRunner((a: string, b: string, k: string, lang: string, useLlm: boolean) =>
    runAudit(a, b, k, lang, useLlm),
  )

  const run = () => {
    if (!left.trim() || !right.trim() || !keys.trim()) {
      runner.setError(t('empty_input'))
      return
    }
    void runner.run(left, right, keys.trim(), i18n.language, llm)
  }

  const clear = () => {
    setLeft(DEMO_LEFT)
    setRight(DEMO_RIGHT)
    setKeys('user_id=uid')
    runner.reset()
  }

  const result = runner.result as AuditResponse | null
  const label = 'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'
  const area =
    'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-8">
      <PageHeader badge="data / joinaudit" maxW="max-w-[620px]" />

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[440px]">
          <Card>
            <label className={label}>{t('left_label')}</label>
            <textarea
              value={left}
              onChange={(e) => setLeft(e.target.value)}
              placeholder={t('data_ph')}
              rows={8}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('right_label')}</label>
            <textarea
              value={right}
              onChange={(e) => setRight(e.target.value)}
              placeholder={t('data_ph')}
              rows={7}
              spellCheck={false}
              className={area}
            />
            <label className={`${label} mt-3`}>{t('keys_label')}</label>
            <input
              value={keys}
              onChange={(e) => setKeys(e.target.value)}
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
