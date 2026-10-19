import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { ApiError, splitkey } from '@/api'
import { downloadText, smallBtnCls } from '@/ui'

export function SplitKeyPanel({
  sessionId,
  report,
  sample,
  onReport,
  onStatus,
}: {
  sessionId: string
  report: string
  sample: number
  onReport: (report: string) => void
  onStatus: (status: string) => void
}) {
  const { t, i18n } = useTranslation()
  const [conf, setConf] = useState('')
  const [patched, setPatched] = useState('')
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const run = async () => {
    setBusy(true)
    setPatched('')
    try {
      const res = await splitkey({
        session_id: sessionId,
        conf,
        report,
        sample,
        lang: i18n.language,
      })
      onReport(res.report)
      if (res.status) onStatus(res.status)
      setPatched(res.patched_conf ?? '')
    } catch (e) {
      onStatus(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const onUpload = (f: File | undefined) => {
    if (!f) return
    f.text().then((text) => setConf(text.slice(0, 200_000)))
  }

  return (
    <Card>
      <details>
        <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
          {t('spk_accordion')}
        </summary>
        <div className="mt-3 flex flex-col gap-3">
          <textarea
            value={conf}
            onChange={(e) => setConf(e.target.value)}
            placeholder={t('spk_conf_ph')}
            rows={8}
            spellCheck={false}
            className="w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink"
          />
          <div className="flex flex-wrap gap-2">
            <button onClick={run} disabled={busy} className={smallBtnCls}>
              {t('spk_btn')}
            </button>
            <button onClick={() => fileRef.current?.click()} className={smallBtnCls}>
              {t('upload_btn')}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".conf,.hocon,.config,.json,.txt"
              className="hidden"
              onChange={(e) => {
                onUpload(e.target.files?.[0])
                e.target.value = ''
              }}
            />
            {patched && (
              <button
                onClick={() => downloadText('seatunnel_patched.conf', patched)}
                className={smallBtnCls}
              >
                {t('spk_apply_dl')}
              </button>
            )}
          </div>
        </div>
      </details>
    </Card>
  )
}
