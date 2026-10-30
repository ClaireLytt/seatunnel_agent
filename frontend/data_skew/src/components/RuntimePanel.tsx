import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { ApiError, runtimeEventlog, runtimeFlink, runtimeHistoryServer } from '@/api'
import { fieldCls, labelCls, smallBtnCls } from '@/ui'

export function RuntimePanel({
  sessionId,
  report,
  onReport,
  onStatus,
  onNote,
}: {
  sessionId: string
  report: string
  onReport: (report: string) => void
  onStatus: (status: string) => void
  onNote: (note: string) => void
}) {
  const { t, i18n } = useTranslation()
  const [url, setUrl] = useState('')
  const [appId, setAppId] = useState('')
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const wrap = async (call: () => Promise<{ report: string; status: string }>) => {
    setBusy(true)
    onNote(t('rt_running'))
    try {
      const res = await call()
      onReport(res.report)
      if (res.status) onStatus(res.status)
    } catch (e) {
      onStatus(e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusy(false)
      onNote('')
    }
  }

  const fetchServer = () =>
    wrap(() =>
      runtimeHistoryServer({
        url,
        app_id: appId,
        report,
        lang: i18n.language,
        session_id: sessionId,
      }),
    )

  const fetchFlink = () =>
    wrap(() =>
      runtimeFlink({
        url,
        app_id: appId,
        report,
        lang: i18n.language,
        session_id: sessionId,
      }),
    )

  const onUpload = (f: File | undefined) => {
    if (!f) return
    void wrap(() => runtimeEventlog(f, report, i18n.language, sessionId))
  }

  return (
    <Card>
      <details>
        <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
          {t('rt_accordion')}
        </summary>
        <div className="mt-3 flex flex-col gap-3">
          <div className="flex gap-3">
            <div className="flex-[2]">
              <label className={labelCls}>{t('rt_url')}</label>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="http://host:18080"
                className={fieldCls}
              />
            </div>
            <div className="flex-[2]">
              <label className={labelCls}>{t('rt_app')}</label>
              <input
                value={appId}
                onChange={(e) => setAppId(e.target.value)}
                placeholder="application_…"
                className={fieldCls}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={fetchServer} disabled={busy} className={smallBtnCls}>
              {t('rt_btn')}
            </button>
            <button onClick={fetchFlink} disabled={busy} className={smallBtnCls}>
              {t('rt_flink_btn')}
            </button>
            <button
              onClick={() => fileRef.current?.click()}
              disabled={busy}
              className={smallBtnCls}
            >
              {t('rt_upload_btn')}
            </button>
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              onChange={(e) => {
                onUpload(e.target.files?.[0])
                e.target.value = ''
              }}
            />
          </div>
        </div>
      </details>
    </Card>
  )
}
