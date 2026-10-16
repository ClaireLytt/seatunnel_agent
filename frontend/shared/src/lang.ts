// Language follows the hub's st-lang cookie (set on the landing page).
export function langFromCookie(): 'en' | 'zh' {
  const m = document.cookie.match(/(?:^|;\s*)st-lang=([^;]+)/)
  return m && decodeURIComponent(m[1]).startsWith('zh') ? 'zh' : 'en'
}
