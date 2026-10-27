for #21 (data skew) — quality close-out after #147

## Summary

A dedupe pass over the line's own accretion (13 PRs' worth), via the repo's dedupe workflow: scan, adjudicate, converge, prove no behavior change.

```diff
 drift.py
+  TREND_DEPTH = 50                 # was a magic number at 7 call sites
+  drift_for(history, table, col)   # the one trend-read + compute call
 api.py / mcp_server.py / runtime.py / cli_cmds/skew.py
-  compute_drift(t, history.splitkey_trend(t, n=50), ...)   # x7
+  drift_for(history, t, ...)

 cli_cmds/skew.py
+  _save_report(path, text)         # -o save + "report saved" notice
-  five hand-rolled copies of that pair
```

Deliberate non-merges, recorded with reasons: the two webhook payload builders (different kinds/fields; `post_webhook` already shared) and the `n=8` display depth in skew-stats (display, not evaluation).

## Evidence

- No behavior change is the acceptance criterion: full `pytest -q` -> **3520 passed, 1 skipped** — identical to before the refactor, zero test edits; ruff clean; mypy Success (175 files).
- Scan table, adjudications and per-group call-site counts: `docs/reports/20261028-skew-dedupe.md`.

## Merge Danger

**Door:** two-way

**Blast Radius:** none intended — internal call-site rewiring only; public signatures untouched.
