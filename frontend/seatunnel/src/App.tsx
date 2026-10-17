import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { fetchMeta, type Meta } from '@/api'

// Walking-skeleton shell: header/topbar + sidebar/chat placeholders.
// Chat, sessions, connect controls land in later tickets.
export default function App() {
  const { t, i18n } = useTranslation()
  const zh = i18n.language.startsWith('zh')

  const [meta, setMeta] = useState<Meta | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchMeta()
      .then(setMeta)
      .catch((e) => setError(String(e)))
  }, [])

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
        <aside className="st-sidebar w-[280px] shrink-0">
          <Card>
            <h2 className="mb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {t('sessions')}
            </h2>
            <p className="font-mono text-sm text-muted">{t('noSessions')}</p>
          </Card>
        </aside>

        <main className="st-chat flex min-h-[60vh] flex-1 flex-col">
          <Card className="flex flex-1 flex-col">
            <div className="flex flex-1 items-center justify-center font-mono text-sm text-muted">
              {error ? error : t('chatEmpty')}
            </div>
            <div className="mt-4 border-t border-line pt-4">
              <input
                className="w-full rounded border border-line bg-card px-3 py-2 font-mono text-sm text-fg outline-none focus:border-ink"
                placeholder={t('inputPlaceholder')}
                disabled
                aria-label={zh ? '消息输入' : 'Message input'}
              />
            </div>
          </Card>
        </main>
      </div>
    </div>
  )
}
