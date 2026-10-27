for #21 (data skew) — follow-up to #138

## Summary

`skew-stats` becomes the one-glance patrol review: each table's trend line now ends with its live drift state, and the summary counts drifting tables.

```diff
 skew-stats
   分片键巡检（每表最近趋势）
-  ⛔ orders  key=region  bad  ×8 次 · top1 72% → 75% → 80%
+  ⛔ orders  key=region  bad  ×8 次 · top1 72% → 75% → 80%  📈漂移
+  ✅ t_ok    key=id      good ×6 次 · top1 10% → 11% → 12%  📊稳定
+  ✅ t_new   key=id      good ×1 次 · top1 5%              —暂无基线
+  漂移中 1 表（详情见 skew-drift）
```

Computed offline from the existing patrol history via the shared `compute_drift` — no new storage, no live SQL.

## Evidence

- **Before:** reviewing which tables are currently drifting meant digging through raw mode=drift records in the generic history listing.
  **After:** `tests/test_data_skew.py` asserts all three states and the summary count render in `skew-stats` — 209 passed; full `pytest -q` -> **3513 passed, 1 skipped**; ruff clean; mypy Success (175 files).
- Batch report: `docs/reports/20261028-skew-stats-drift.md`.

## Merge Danger

**Door:** two-way

Console-output addition only; no schema, endpoint or payload changes.

**Blast Radius:** minimal

Scripts that parse skew-stats trend lines would see a trailing status token.
