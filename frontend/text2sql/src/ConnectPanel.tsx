import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import {
  connect,
  fetchDatasources,
  type Datasource,
  type DbConfig,
  type DsType,
  type SessionMeta,
} from '@/api'

const inputCls =
  'w-full rounded border border-line bg-card px-3 py-2 font-mono text-sm text-fg ' +
  'outline-none focus:border-ink'
const labelCls = 'mb-1 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

// sqlite only needs a file path; everything else takes host/port/user/pass.
const needsServer = (ds: DsType) => ds !== 'sqlite'

export function ConnectPanel({ onConnected }: { onConnected: (s: SessionMeta) => void }) {
  const { t } = useTranslation()
  const [sources, setSources] = useState<Datasource[]>([])
  const [ds, setDs] = useState<DsType>('hive')
  const [cfg, setCfg] = useState<DbConfig>({})
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')

  useEffect(() => {
    fetchDatasources().then(setSources).catch(console.error)
  }, [])

  // env-derived defaults prefill the form whenever the dialect changes
  const pick = (next: DsType) => {
    setDs(next)
    setCfg(sources.find((s) => s.ds_type === next)?.defaults ?? {})
  }

  const set = (k: keyof DbConfig) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setCfg((c) => ({ ...c, [k]: e.target.value }))

  const onConnect = async () => {
    setBusy(true)
    setStatus('')
    try {
      const meta = await connect(ds, cfg)
      setStatus(t('connected', { count: meta.table_count }))
      onConnected(meta)
    } catch (e) {
      setStatus(t('connectFailed', { msg: e instanceof Error ? e.message : String(e) }))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="st-connect space-y-3">
      <div>
        <label className={labelCls} htmlFor="ds">
          {t('dsType')}
        </label>
        <select id="ds" className={inputCls} value={ds} onChange={(e) => pick(e.target.value)}>
          {(sources.length ? sources.map((s) => s.ds_type) : ['hive']).map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </div>
      {needsServer(ds) && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelCls} htmlFor="f-host">
              {t('host')}
            </label>
            <input id="f-host" className={inputCls} value={cfg.host ?? ''} onChange={set('host')} />
          </div>
          <div>
            <label className={labelCls} htmlFor="f-port">
              {t('port')}
            </label>
            <input id="f-port" className={inputCls} value={cfg.port ?? ''} onChange={set('port')} />
          </div>
          <div>
            <label className={labelCls} htmlFor="f-username">
              {t('username')}
            </label>
            <input
              id="f-username"
              className={inputCls}
              value={cfg.username ?? ''}
              onChange={set('username')}
            />
          </div>
          <div>
            <label className={labelCls} htmlFor="f-password">
              {t('password')}
            </label>
            <input
              id="f-password"
              type="password"
              className={inputCls}
              value={cfg.password ?? ''}
              onChange={set('password')}
            />
          </div>
        </div>
      )}
      <div>
        <label className={labelCls} htmlFor="f-database">
          {t('database')}
        </label>
        <input
          id="f-database"
          className={inputCls}
          value={cfg.database ?? ''}
          onChange={set('database')}
          placeholder={ds === 'sqlite' ? 'config/uitest_demo.db' : ''}
        />
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={onConnect}
          disabled={busy}
          className="rounded border-[1.5px] border-ink bg-ink px-5 py-2 font-mono text-sm text-paper transition enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard disabled:opacity-50"
        >
          {busy ? t('connecting') : t('connect')}
        </button>
        <span className="st-connect-status font-mono text-sm text-muted">
          {status || t('notConnected')}
        </span>
      </div>
    </Card>
  )
}
