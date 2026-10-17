import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { connectSide, type Datasource } from '@/api'
import { Card } from '@shared/components/card'

const inputCls =
  'w-full rounded border border-line bg-card px-2.5 py-1.5 font-mono text-[13px] text-fg ' +
  'outline-none focus:border-ink'

const labelCls = 'mb-1 block font-mono text-[10px] uppercase tracking-[0.16em] text-ink-soft'

export function ConnectForm({
  side,
  datasources,
  sessionId,
  table,
  onTable,
}: {
  side: 'a' | 'b'
  datasources: Datasource[]
  sessionId: string
  table: string
  onTable: (t: string) => void
}) {
  const { t, i18n } = useTranslation()

  const [dsKey, setDsKey] = useState(datasources[0]?.key ?? 'hive')
  const [host, setHost] = useState('')
  const [port, setPort] = useState('')
  const [db, setDb] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [tables, setTables] = useState<string[]>([])

  const ds = datasources.find((d) => d.key === dsKey)

  const onConnect = async () => {
    setBusy(true)
    setStatus('')
    try {
      const r = await connectSide({
        session_id: sessionId,
        side,
        ds_type: dsKey,
        host,
        port,
        db,
        username,
        password,
        lang: i18n.language.startsWith('zh') ? 'zh' : 'en',
      })
      if (r.ok) {
        setStatus(r.status)
        setTables(r.tables)
        onTable('')
        // backfill env/default fallbacks like the legacy page
        if (dsKey !== 'sqlite') {
          setHost(r.resolved.host)
          setPort(String(r.resolved.port))
        }
        setDb(r.resolved.database)
      } else {
        setStatus(r.error)
        setTables([])
        onTable('')
      }
    } catch (e) {
      setStatus(`❌ ${e instanceof Error ? e.message : e}`)
    } finally {
      setBusy(false)
    }
  }

  const sideLabel = side === 'a' ? t('sourceA') : t('sourceB')
  const ok = status.startsWith('✅')

  return (
    <section data-testid={`connect-${side}`}>
      <Card>
      <div className="mb-3 flex items-center justify-between">
        <span className="font-display text-base font-bold text-ink">{sideLabel}</span>
        <span className="rounded border border-ink-soft px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-soft">
          {side}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className={labelCls} htmlFor={`ds-${side}`}>
            {t('dsType')}
          </label>
          <select
            id={`ds-${side}`}
            className={inputCls}
            value={dsKey}
            onChange={(e) => setDsKey(e.target.value)}
          >
            {datasources.map((d) => (
              <option key={d.key} value={d.key}>
                {d.label}
              </option>
            ))}
          </select>
        </div>

        {ds?.needs_host && (
          <>
            <div>
              <label className={labelCls} htmlFor={`host-${side}`}>
                {t('host')}
              </label>
              <input
                id={`host-${side}`}
                className={inputCls}
                value={host}
                onChange={(e) => setHost(e.target.value)}
                placeholder="127.0.0.1"
              />
            </div>
            <div>
              <label className={labelCls} htmlFor={`port-${side}`}>
                {t('port')}
              </label>
              <input
                id={`port-${side}`}
                className={inputCls}
                value={port}
                onChange={(e) => setPort(e.target.value)}
                placeholder={String(ds.default_port)}
              />
            </div>
          </>
        )}

        <div className="col-span-2">
          <label className={labelCls} htmlFor={`db-${side}`}>
            {t('database')}
          </label>
          <input
            id={`db-${side}`}
            className={inputCls}
            value={db}
            onChange={(e) => setDb(e.target.value)}
            placeholder={ds?.default_db || 'default'}
          />
        </div>

        {ds?.needs_auth && (
          <>
            <div>
              <label className={labelCls} htmlFor={`user-${side}`}>
                {t('username')}
              </label>
              <input
                id={`user-${side}`}
                className={inputCls}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="off"
              />
            </div>
            <div>
              <label className={labelCls} htmlFor={`pwd-${side}`}>
                {t('password')}
              </label>
              <input
                id={`pwd-${side}`}
                type="password"
                className={inputCls}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
          </>
        )}
      </div>

      <div className="mt-3 flex items-center gap-3">
        <button
          onClick={onConnect}
          disabled={busy || !sessionId}
          className="rounded border-[1.5px] border-ink bg-ink px-5 py-1.5 font-mono text-[13px] text-paper transition enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard disabled:opacity-50"
        >
          {busy ? t('connecting') : t('connect')}
        </button>
        {status && (
          <span
            data-testid={`status-${side}`}
            className="min-w-0 flex-1 truncate font-mono text-[12px]"
            style={{ color: ok ? 'var(--ok)' : 'var(--accent)' }}
            title={status}
          >
            {status}
          </span>
        )}
      </div>

      <div className="mt-3">
        <label className={labelCls} htmlFor={`table-${side}`}>
          {t('selectTable')}
        </label>
        <select
          id={`table-${side}`}
          className={inputCls}
          value={table}
          onChange={(e) => onTable(e.target.value)}
          disabled={tables.length === 0}
        >
          <option value=""></option>
          {tables.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        </div>
      </Card>
    </section>
  )
}
