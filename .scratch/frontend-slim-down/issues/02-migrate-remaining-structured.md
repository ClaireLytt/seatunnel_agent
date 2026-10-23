# 02: Migrate the remaining 9 structured-error workspaces to postStructured

**What to build:** Users of change_impact, config_lint, config_migrate, data_lineage, data_skew, pii_scan, schema_drift, sql_fmt and sql_transpile see identical behavior (same requests, same localized error banners), while every remaining copy of the structured-error fetch block is deleted in favor of the shared `postStructured` (contract step — grep finds zero copies).

**Blocked by:** 01 (Expand: postStructured in shared api + pilot migration).

**Status:** done (2026-10-23) — scope adjusted: 6 of 9 migrated; change_impact/data_lineage/data_skew kept their own ApiError semantics (see docs/reports/20261023-frontend-slim-down.md)

- [x] Zero hand-rolled structured-error fetch blocks remain in workspace api clients (verifiable by grep)
- [x] Exported function signatures, types, and endpoint paths unchanged in all 9 workspaces
- [x] `npm run lint`/`npm run build` for each touched workspace pass; affected Playwright page tests green
