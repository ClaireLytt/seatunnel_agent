import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'

export default function App() {
  const { t } = useTranslation()
  return (
    <div className="mx-auto max-w-[1020px] px-4 py-10">
      <motion.header
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex items-start justify-between"
      >
        <div>
          <span className="mb-4 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
            devops / uitest
          </span>
          <h1 className="font-display text-4xl font-bold tracking-tight text-ink">{t('title')}</h1>
          <p className="mt-3 max-w-[620px] text-muted">{t('subtitle')}</p>
        </div>
        <a
          href="/"
          title={t('home')}
          className="rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard"
        >
          {t('home')}
        </a>
      </motion.header>
      {/* Run panel, progress, report — batch 3 */}
    </div>
  )
}
