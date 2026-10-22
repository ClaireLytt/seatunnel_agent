import { useTranslation } from 'react-i18next'

import { btnGhost } from '../constants'

/**
 * Standard page header: badge + i18n `title` / `subtitle` + home link
 * (i18n `home`). Class names mirror the doc_qa page verbatim; the outer
 * container width is the caller's concern. `titlePrefix` carries a page's
 * emoji so headers can unify without a visible copy change.
 */
export function PageHeader({
  badge,
  maxW = 'max-w-[680px]',
  titlePrefix = '',
}: {
  badge: string
  maxW?: string
  titlePrefix?: string
}) {
  const { t } = useTranslation()
  return (
    <header className="flex items-start justify-between gap-4">
      <div>
        <span className="mb-4 inline-block rounded border border-ink-soft px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
          {badge}
        </span>
        <h1 className="font-display text-4xl font-bold tracking-tight text-ink">
          {titlePrefix ? `${titlePrefix} ` : ''}
          {t('title')}
        </h1>
        <p className={`mt-3 ${maxW} text-muted`}>{t('subtitle')}</p>
      </div>
      <a href="/" title={t('home')} className={btnGhost}>
        {t('home')}
      </a>
    </header>
  )
}
