import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { connect, fetchMeta, type Meta } from '@/api'
import { Chat } from '@/Chat'

const inputCls =
  'w-full rounded border border-line bg-card px-3 py-2 font-mono text-sm text-fg ' +
  'outline-none focus:border-ink'
const labelCls = 'mb-1 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

// Shell: header/topbar + sidebar placeholder + chat.
// Shell: header + sidebar (sessions placeholder, connect controls) + chat.
// Sessions persistence lands in a later ticket.
export default function App() {
  const { t, i18n } = useTranslation()
  const zh = i18n.language.startsWith('zh')

  const [meta, setMeta] = useState<Meta | null>(null)
  const [error, setError] = useState('')
  const [mode, setMode] = useState('nl')
  const [configPath, setConfigPath] = useState('')
  const [template, setTemplate] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [status, setStatus] = useState('')

  useEffect(() => {
    fetchMeta()
      .then(setMeta)
      .catch((e) => setError(String(e)))
  }, [])

  // legacy ui.py _template_to_prompt: selecting a template fills the input
  const selectedTpl = meta?.templates.find((tp) => tp.name === template)
  const templatePrompt = selectedTpl
    ? t('templatePrompt', {
        name: selectedTpl.name,
        params: selectedTpl.parameters
          .filter((p) => p.default)
          .map((p) => `${p.name}=${p.default}`)
          .join(', '),
      })
    : ''

  const onConnect = async () => {
    setConnecting(true)
    try {
      const res = await connect()
      setStatus(
        res.ok ? t('connected', { model: res.model }) : t('connectFailed', { error: res.error }),
      )
    } catch (e) {
      setStatus(t('connectFailed', { error: e instanceof Error ? e.message : String(e) }))
    } finally {
      setConnecting(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-[1280px] flex-col gap-4 px-4 py-6">
      <header className="flex items-end justify-between border-b border-line pb-4">
        <div>
          <span className="mb-2 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            data / seatunnel
          </span>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink">{t('title')}</h1>
          <p className="mt-1 text-sm text-muted">{t('subtitle')}</p>
        </div>
        <nav className="flex items-center gap-4 font-mono text-sm">
          {meta && (
            <span className="text-ink-soft">
              {t('mode')} ×{meta.modes.length} · {t('templates')} ×{meta.templates.length}
            </span>
          )}
          <a href="/" className="text-ink underline-offset-4 hover:underline">
            {t('home')}
          </a>
        </nav>
      </header>

      <div className="flex flex-1 gap-4">
        <aside className="st-sidebar flex w-[280px] shrink-0 flex-col gap-4">
          <Card>
            <h2 className="mb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('sessions')}
            </h2>
            <p className="font-mono text-sm text-muted">{t('noSessions')}</p>
          </Card>

          <Card className="st-config space-y-3">
            <div>
              <label className={labelCls} htmlFor="st-mode">
                {t('mode')}
              </label>
              <select
                id="st-mode"
                className={inputCls}
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                {(meta?.modes ?? []).map((m) => (
                  <option key={m.key} value={m.key}>
                    {zh ? m.zh : m.en}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelCls} htmlFor="st-config-path">
                {t('configPath')}
              </label>
              <input
                id="st-config-path"
                className={inputCls}
                value={configPath}
                onChange={(e) => setConfigPath(e.target.value)}
                placeholder={meta?.config_placeholder ?? ''}
              />
            </div>
            <div>
              <label className={labelCls} htmlFor="st-template">
                {t('templates')}
              </label>
              <select
                id="st-template"
                className={inputCls}
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
              >
                <option value="">{t('tplNone')}</option>
                {(meta?.templates ?? []).map((tp) => (
                  <option key={tp.name} value={tp.name}>
                    {tp.name} ({tp.description})
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={onConnect}
              disabled={connecting}
              className="st-connect-btn w-full rounded border-[1.5px] border-ink bg-ink px-5 py-2 font-mono text-sm text-paper transition enabled:hover:-translate-x-px enabled:hover:-translate-y-px enabled:hover:shadow-hard disabled:opacity-50"
            >
              {connecting ? t('connecting') : t('connect')}
            </button>
            <div>
              <span className={labelCls}>{t('status')}</span>
              <p className="st-status break-words font-mono text-sm text-muted" role="status">
                {status || t('statusDefault')}
              </p>
            </div>
          </Card>
        </aside>

        <main className="st-chat flex min-h-[60vh] flex-1 flex-col">
          <Card className="flex flex-1 flex-col">
            <Chat
              emptyHint={error ? error : t('chatEmpty')}
              mode={mode}
              configPath={configPath}
              templatePrompt={templatePrompt}
              onConfigPath={setConfigPath}
            />
          </Card>
        </main>
      </div>
    </div>
  )
}
