// Language follows the hub's st-lang cookie (set on the landing page).
export function langFromCookie(): 'en' | 'zh' {
  const m = document.cookie.match(/(?:^|;\s*)st-lang=([^;]+)/)
  return m && decodeURIComponent(m[1]).startsWith('zh') ? 'zh' : 'en'
}

// Normalize an i18next instance's language to the API's zh/en pair.
export function langOf(i18n: { language: string }): 'en' | 'zh' {
  return i18n.language.startsWith('zh') ? 'zh' : 'en'
}
