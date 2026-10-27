for #21 (data skew); also carries the chat-bi line for #35 (branch `skew` was fast-forwarded onto `origin/uiskill` at the user's request, so the 67 chat-bi/text2sql commits ride along — see `docs/PR_DRAFT_uiskill.md` for that line's own summary)

## Summary

Skew drift detection and runtime re-checks: every split-key patrol measurement now feeds a per-(table, key) time series, and both the patrol and the runtime diagnosis compare "now" against "before".

```text
skew-splitkey run
  measure key (top1 / ndv / null)        # existing
  log to history                         # existing
  drift tail: latest vs baseline (median of earlier runs, same table+key)
    insufficient (<3 measured runs) | stable | DRIFT (+metric deltas)
  webhook: payload gains drift_tables + drift text (fires on drift alone)

skew-drift [TABLE] [--fail] [--webhook]  # offline, reads history only
skew-runtime <eventlog|history-server>
  re-check line vs previous diagnosis of the same app (better/worse/unchanged)
```

Facade parity — the same `compute_drift`/`render_drift` core behind every entry point:

```diff
 agents/data/data_skew/
+├── drift.py            # baseline median; thresholds +10pp top1 / +5pp null / -30% ndv
 ├── history.py
+│     last_runtime(), log_drift()
 ├── runtime.py
+│     diagnose_and_log()   # one shared tail for CLI/REST/MCP (was 4 copies)
 ├── api.py               +GET /api/skew/drift
 ├── mcp_server.py        +skew_drift tool (also in the no-db profile)
 frontend/data_skew/
+└── components/DriftCard.tsx   # verdict badge + per-metric deltas
```

Also in this push: the `check_workflow.py` attribution scan no longer trips on trailers merged from main (dependabot), and the floor check treats numeric-only assert updates as updates, not deleted assertions.

## Evidence

- **Before:** each patrol was judged in isolation — a key drifting 12% to 28% top-1 share stayed silent until it crossed a hard threshold; runtime diagnoses never compared across runs.
  **After:** `tests/test_data_skew.py` 178 -> 199 passed (drift core, per-column series, CLI gates, webhook payload, MCP, REST); browser suite `pytest -m uitest tests/test_dataskew_page.py` 20 -> 21 passed (DriftCard renders `top1_pct: 12 -> 28 (+16)` from seeded history).
- Full suite: `pytest -q` -> **3503 passed, 1 skipped**; `ruff` clean; `mypy` Success (175 files); uitest smoke 16/16 (`runs/20261027_233930/report.html`).
- Batch reports with pasted command tails under `docs/reports/20261027-skew-drift-*.md` and `docs/reports/20261028-skew-*.md`.

## Merge Danger

**Door:** two-way

Pure addition on the skew side: new module, new endpoints, new card; the only shared-behavior change is the splitkey webhook payload, which stays byte-identical when nothing drifts.

**Blast Radius:** small

A new `drift_tables` field appears in splitkey webhook payloads when a drift exists — consumers that strictly validate payload schemas would need to allow it. The chat-bi commits carried from `uiskill` have their own (larger) radius, documented in `docs/PR_DRAFT_uiskill.md`.
