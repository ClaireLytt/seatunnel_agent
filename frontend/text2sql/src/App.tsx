import { useState } from 'react'
import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { ConnectPanel } from '@/ConnectPanel'
import type { SessionMeta } from '@/api'

export default function App() {
  const { t } = useTranslation()
  const [session, setSession] = useState<SessionMeta | null>(null)

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
        <ConnectPanel onConnected={setSession} />
        <div className="flex gap-4 font-mono text-sm">
          <a href="/" className="text-ink underline-offset-4 hover:underline">
            {t('home')}
          </a>
          <a href="/text2sql" className="text-muted underline-offset-4 hover:underline">
            {t('legacy')}
          </a>
        </div>
      </motion.aside>

      <main className="min-h-[70vh] flex-1">
        {/* Chat panel lands in ticket #65; until then show the session state */}
        {session && (
          <div className="st-session rounded border border-line bg-card p-4 font-mono text-sm text-fg">
            session {session.session_id.slice(0, 8)}… · {session.ds_type} · {session.table_count}{' '}
            tables
          </div>
        )}
      </main>
    </div>
  )
}
