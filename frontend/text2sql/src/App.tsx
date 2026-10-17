import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { ChatPanel } from '@/ChatPanel'
import { FavoritesView } from '@/FavoritesView'
import { HistoryView } from '@/HistoryView'
import { SchemaBrowser } from '@/SchemaBrowser'
import { SchemaPanel } from '@/SchemaPanel'
import { ConnectPanel } from '@/ConnectPanel'
import type { SessionMeta } from '@/api'

export default function App() {
  const { t } = useTranslation()
  const [session, setSession] = useState<SessionMeta | null>(null)
  const [fullTables, setFullTables] = useState<string[]>([])
  const viewFromHash = () =>
    location.hash === '#schema'
      ? 'schema'
      : location.hash === '#history'
        ? 'history'
        : location.hash === '#favorites'
          ? 'favorites'
          : 'chat'
  const [view, setView] = useState(viewFromHash())
  const [seed, setSeed] = useState<{ role: string; content: string }[] | undefined>()

  useEffect(() => {
    const onHash = () => setView(viewFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const connected = (s: SessionMeta) => {
    setSession(s)
    setFullTables(s.tables)
  }

  return (
    <div className="mx-auto flex max-w-[1280px] gap-6 px-4 py-8">
      <motion.aside
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.4 }}
        className="w-[360px] shrink-0 space-y-4"
      >
        <div>
          <span className="mb-3 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            data / text2sql
          </span>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink">{t('title')}</h1>
          <p className="mt-2 text-sm text-muted">{t('subtitle')}</p>
        </div>
        <ConnectPanel onConnected={connected} />
        {session && (
          <SchemaPanel
            session={session}
            fullTables={fullTables}
            onSession={setSession}
            onFullTables={setFullTables}
          />
        )}
        <div className="flex gap-4">
          <a
            href="#history"
            className="font-mono text-sm text-ink underline-offset-4 hover:underline"
          >
            {t('history')}
          </a>
          <a
            href="#favorites"
            className="font-mono text-sm text-ink underline-offset-4 hover:underline"
          >
            ⭐ {t('favorites')}
          </a>
        </div>
        {session && (
          <a
            href={view === 'schema' ? '#' : '#schema'}
            className="font-mono text-sm text-ink underline-offset-4 hover:underline"
          >
            {view === 'schema' ? t('backToChat') : t('schemaBrowser')}
          </a>
        )}
        <div className="st-legacy-links rounded border border-line bg-card p-3 font-mono text-[12px]">
          <div className="mb-1 uppercase tracking-[0.18em] text-ink-soft">{t('pending')}</div>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {['templates', 'metrics', 'subscriptions', 'boards'].map(
              (k) => (
                <a
                  key={k}
                  href="/text2sql-legacy"
                  className="text-muted underline-offset-4 hover:underline"
                >
                  {t(k)}
                </a>
              ),
            )}
          </div>
        </div>
        <div className="flex gap-4 font-mono text-sm">
          <a href="/" className="text-ink underline-offset-4 hover:underline">
            {t('home')}
          </a>
          <a href="/text2sql-legacy" className="text-muted underline-offset-4 hover:underline">
            {t('legacy')}
          </a>
        </div>
      </motion.aside>

      <main className="min-h-[70vh] flex-1">
        {view === 'favorites' ? (
          <FavoritesView />
        ) : view === 'history' ? (
          <HistoryView
            session={session}
            onResume={(_title, chat) => {
              setSeed([...chat])
              location.hash = ''
            }}
          />
        ) : session && view === 'schema' ? (
          <SchemaBrowser session={session} />
        ) : session ? (
          <ChatPanel session={session} onSessionReset={setSession} seed={seed} />
        ) : (
          <div className="st-session rounded border border-line bg-card p-4 font-mono text-sm text-muted">
            —
          </div>
        )}
      </main>
    </div>
  )
}
