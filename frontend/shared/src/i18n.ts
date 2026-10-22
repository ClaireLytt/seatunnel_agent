import i18n from 'i18next'
import type { Resource } from 'i18next'
import { initReactI18next } from 'react-i18next'

import { langFromCookie } from './lang'

/**
 * Shared i18next bootstrap — a page's i18n.ts keeps only its dictionary and
 * ends with `export default initI18n(resources)`.
 */
export function initI18n(resources: Resource) {
  void i18n.use(initReactI18next).init({
    resources,
    lng: langFromCookie(),
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
  })
  return i18n
}
