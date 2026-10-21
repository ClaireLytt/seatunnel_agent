import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { readConnHandoff } from '@/connHandoff'
import {
  ApiError,
  connect,
  consistency,
  presetGet,
  presetsList,
  verify,
  type PresetSummary,
} from '@/api'
import { fieldCls, labelCls, smallBtnCls } from '@/ui'

// Probe queries use GROUP BY ... ORDER BY ... LIMIT — restrict the panel
// to LIMIT-compatible engines (legacy _PROBE_DS).
const DS_CHOICES: [string, string][] = [
  ['Hive', 'hive'],
  ['Spark SQL', 'sparksql'],
  ['MySQL', 'mysql'],
  ['PostgreSQL', 'postgresql'],
  ['SQLite', 'sqlite'],
]

// Port/database placeholders per datasource (legacy DS_DEFAULTS subset).
const DS_PLACEHOLDERS: Record<string, { port: string; db: string }> = {
  hive: { port: '10000', db: 'default' },
  sparksql: { port: '10001', db: 'default' },
  mysql: { port: '3306', db: '' },
  postgresql: { port: '5432', db: 'postgres' },
  sqlite: { port: '', db: 'config/demo.db' },
}

export function ConnectPanel({
  sessionId,
  sql,
  dialect,
  optimized,
  report,
  sample,
  setSample,
  onReport,
  onNote,
}: {
  sessionId: string
  sql: string
  dialect: string
  optimized: string
  report: string
  sample: number
  setSample: (n: number) => void
  onReport: (report: string) => void
  onNote: (note: string) => void
}) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const [presets, setPresets] = useState<PresetSummary[]>([])
  const [preset, setPreset] = useState('')
  const [ds, setDs] = useState('hive')
  const [host, setHost] = useState('')
  const [port, setPort] = useState('')
  const [db, setDb] = useState('')
  const [user, setUser] = useState('')
  const [pwd, setPwd] = useState('')
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    // connection handed over from Data Comparison (cookie, no password):
    // pre-fill the form and open the accordion
    const handed = readConnHandoff()
    if (!handed || !handed.ds_type) return
    setOpen(true)
    if (!DS_CHOICES.some(([, v]) => v === handed.ds_type)) {
      setStatus(t('conn_handoff_unsupported', { t: handed.ds_type }))
      return
    }
    setDs(handed.ds_type)
    setHost(handed.host)
    setPort(handed.port)
    setDb(handed.database)
    setUser(handed.username)
    setStatus(
      t('conn_handoff', {
        ds: handed.ds_type,
        host: handed.host,
        port: handed.port,
        db: handed.database,
      }),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadPresets = async () => {
    try {
      const { presets: list } = await presetsList()
      setPresets(list)
      if (!list.length) setStatus(t('preset_none'))
    } catch {
      setPresets([])
      setStatus(t('preset_none'))
    }
  }

  const pickPreset = async (name: string) => {
    setPreset(name)
    if (!name) return
    const summary = presets.find((p) => p.name === name)
    if (summary && !summary.supported) {
      setStatus(t('preset_unsupported', { t: summary.ds_type }))
      return
    }
    try {
      const p = await presetGet(name)
      setDs(p.ds_type)
      setHost(p.host)
      setPort(p.port)
      setDb(p.database)
      setUser(p.username)
      setPwd(p.password)
    } catch {
      /* preset vanished — leave the form as-is */
    }
  }

  const doConnect = async () => {
    setBusy(true)
    try {
      const res = await connect({
        session_id: sessionId,
        ds_type: ds,
        host,
        port,
        database: db,
        username: user,
        password: pwd,
        lang: i18n.language,
      })
      setStatus(res.status)
    } catch (e) {
      setStatus(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const sectionCall = async (
    note: string,
    call: () => Promise<{ report: string; status: string }>,
  ) => {
    setBusy(true)
    onNote(note)
    try {
      const res = await call()
      onReport(res.report)
      setStatus(res.status || status)
    } catch (e) {
      if (e instanceof ApiError) setStatus(e.message)
      else setStatus(String(e))
    } finally {
      setBusy(false)
      onNote('')
    }
  }

  const doVerify = () =>
    sectionCall(t('verify_running'), () =>
      verify({
        session_id: sessionId,
        sql,
        report,
        dialect,
        sample,
        lang: i18n.language,
      }),
    )

  const doConsistency = () =>
    sectionCall(t('cst_running'), () =>
      consistency({
        session_id: sessionId,
        sql,
        optimized,
        report,
        lang: i18n.language,
      }),
    )

  return (
    <Card>
      <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
          {t('conn_accordion')}
        </summary>
        <div className="mt-3 flex flex-col gap-3">
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label className={labelCls}>{t('preset_dd')}</label>
              <select
                value={preset}
                onChange={(e) => pickPreset(e.target.value)}
                className={fieldCls}
              >
                <option value=""></option>
                {presets.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <button onClick={loadPresets} className={smallBtnCls}>
              {t('preset_load')}
            </button>
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className={labelCls}>{t('ds_type')}</label>
              <select value={ds} onChange={(e) => setDs(e.target.value)} className={fieldCls}>
                {DS_CHOICES.map(([label, v]) => (
                  <option key={v} value={v}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className={labelCls}>{t('sample')}</label>
              <select
                value={sample}
                onChange={(e) => setSample(Number(e.target.value))}
                className={fieldCls}
              >
                <option value={0}>{t('sample_full')}</option>
                <option value={10}>10%</option>
                <option value={1}>1%</option>
              </select>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="flex-[2]">
              <label className={labelCls}>{t('host')}</label>
              <input value={host} onChange={(e) => setHost(e.target.value)} className={fieldCls} />
            </div>
            <div className="flex-1">
              <label className={labelCls}>{t('port')}</label>
              <input
                value={port}
                onChange={(e) => setPort(e.target.value)}
                placeholder={DS_PLACEHOLDERS[ds]?.port ?? ''}
                className={fieldCls}
              />
            </div>
          </div>
          <div>
            <label className={labelCls}>{t('db')}</label>
            <input
              value={db}
              onChange={(e) => setDb(e.target.value)}
              placeholder={DS_PLACEHOLDERS[ds]?.db ?? ''}
              className={fieldCls}
            />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className={labelCls}>{t('user')}</label>
              <input value={user} onChange={(e) => setUser(e.target.value)} className={fieldCls} />
            </div>
            <div className="flex-1">
              <label className={labelCls}>{t('pwd')}</label>
              <input
                type="password"
                value={pwd}
                onChange={(e) => setPwd(e.target.value)}
                className={fieldCls}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={doConnect} disabled={busy} className={smallBtnCls}>
              {t('connect_btn')}
            </button>
            <button onClick={doVerify} disabled={busy} className={smallBtnCls}>
              {t('verify_btn')}
            </button>
            <button onClick={doConsistency} disabled={busy} className={smallBtnCls}>
              {t('cst_btn')}
            </button>
          </div>
          <p className="text-sm text-muted">{status || t('conn_status_none')}</p>
        </div>
      </details>
    </Card>
  )
}
