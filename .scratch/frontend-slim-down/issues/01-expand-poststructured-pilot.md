# 01: Expand: postStructured in shared api + pilot migration (dag_check, metric_diff)

**What to build:** When a user runs a check against a bad input (e.g. a missing SQL dir), the page shows exactly the same localized structured-error message as today — but the fetch/parse/throw contract behind it lives once in the shared api module as `postStructured(url, body)`, reproducing the copied block's behavior exactly: non-2xx → parse `detail`; object-with-`code` → legacy `ApiError(code, path, error)`; otherwise `Error(detail || "HTTP <status>")`. The dag_check and metric_diff workspaces are migrated as pilots, their local blocks deleted.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] `postStructured` exists once in the shared api module next to `ApiError`/`fetchJson`, behavior identical to the copied block
- [ ] The two pilot api clients contain only endpoint paths, types, and payload mapping; exported signatures unchanged
- [ ] `npm run lint`/`npm run build` for shared + both workspaces pass; the two pages' Playwright page tests green (success and error paths)
