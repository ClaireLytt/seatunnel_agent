# 09: Schedule + webhook + trends

**What to build:** Scheduled comparisons (interval select, start/stop, server-side timer keyed to the session registry), webhook notification (URL + notify-on-fail, posted server-side), and the trends view: alert rules plus a theme-aware recharts chart fed by trend data from the API (replacing the matplotlib PNG).

**Blocked by:** 04 — Compound actions, 07 — Reports

**Status:** done

- [x] Schedule start/stop/status round-trips; a scheduled run saves its report server-side
- [x] Webhook fires per legacy semantics (testable via a local capture endpoint)
- [x] Trend chart renders from API data with theme tokens, correct in light and dark
- [x] In-process API tests for schedule lifecycle and trend data
- [x] Project verification commands green
