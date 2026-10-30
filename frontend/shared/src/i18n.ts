import i18n from 'i18next'
import type { Resource } from 'i18next'
import { initReactI18next } from 'react-i18next'

import { langFromCookie } from './lang'

/**
 * Shared i18next bootstrap — a page's i18n.ts keeps only its dictionary and
 * ends with `export default initI18n(resources)`.
 *
 * COMMON carries the strings every page repeats verbatim (the review found
 * them copied per app); an app's own key with the same name wins.
 */
const COMMON: Record<string, Record<string, string>> = {
  en: {
    home: 'Home',
    bad_dir: 'Not a directory: ',
    empty_dir: 'Provide a SQL directory first.',
  },
  zh: {
    home: '首页',
    bad_dir: '不是有效目录: ',
    empty_dir: '请先填写 SQL 目录。',
  },
}

export function initI18n(resources: Resource) {
  const merged: Resource = {}
  for (const lang of Object.keys(resources)) {
    const app = (resources[lang] as { translation?: Record<string, unknown> }).translation ?? {}
    merged[lang] = { translation: { ...(COMMON[lang] ?? {}), ...app } }
  }
  void i18n.use(initReactI18next).init({
    resources: merged,
    lng: langFromCookie(),
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
  })
  // the uitest runner waits for this stamp on every page (Gradio pages set
  // it in their load hook); React pages honor the same contract
  try {
    document.body.dataset.stLang = langFromCookie()
  } catch {
    /* non-browser */
  }
  return i18n
}
