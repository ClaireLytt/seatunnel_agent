# 01: SQL Review visual alignment with uitest

**What to build:** The SQL Review page reads like the uitest page: the trend chart's severity colors come from theme tokens (legible in dark mode, same color vocabulary as the uitest counts chart), the report section only appears once a report exists, error messages carry the ❌ prefix convention, and the SQL input label is localized like every other label. No functional change.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Trend chart severities use theme tokens (critical→accent, suggestion→ok, risk→neutral soft-ink); correct in light and dark
- [x] Report heading + card absent until a review produces a report; placeholder i18n strings removed from both locales
- [x] Error messages (review error and stats error) rendered with ❌ prefix
- [x] SQL input label served from i18n in zh and en
- [x] Playwright page test extended: report section absent before review
- [x] Before/after screenshots under docs/reports/shots/
- [x] ruff/pytest + sql_review workspace lint/build green
