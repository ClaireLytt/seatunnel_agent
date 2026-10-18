# 08: Generation features + templates — sync-config / diff-SQL / lineage / multi-environment / template batch

**What to build:** Sync-config generation with download (real passwords preserved in the downloaded file), diff-SQL generation, lineage analysis from SQL, multi-environment compare (env A/B/table), and comparison templates (save/load/delete + multi-select batch run) — all 1:1 with legacy.

**Blocked by:** 05 — Options + presets

**Status:** done

- [x] Sync-config generates and downloads; diff-SQL renders; lineage renders; multi-env compare works
- [x] Templates CRUD + batch run over selected templates
- [x] In-process API tests for sync-config content and template batch contract
- [x] Project verification commands green
