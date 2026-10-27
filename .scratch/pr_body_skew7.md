for #21 (data skew) — follow-up to #140

## Summary

Sink-side distribution keys join the drift machinery source keys already have.

```diff
 sink_key_section (shared by CLI / REST / MCP splitkey checks)
   measure each sink key (bucket / sharding / partition_by) on the source rows
   render the sink sub-section
+  log each table-identified sink key into the splitkey history
+    (verdict + top1/ndv/null + hot value; skipped when the sink has no
+     resolvable table — a trend needs a stable identity, no guessing)
```

Downstream, with zero extra code: sink tables now get `skew-stats` trend lines, `skew-drift` baselines/alerts/recovery cards, and the hot-value identity line.

## Evidence

- **Before:** a ClickHouse `sharding_key` measuring 80% hot showed up in one report and vanished — no trend, no drift baseline, no stats row.
  **After:** three checkup runs produce three history records (`dw.orders`/`region`/`bad`/`top1 80%/CN`) and `skew-drift dw.orders` answers with a baseline verdict — asserted in `tests/test_data_skew.py` (211 passed); default behavior without `log_source` is unchanged (asserted). Full `pytest -q` -> **3515 passed, 1 skipped**; ruff clean; mypy Success (175 files).
- Batch report: `docs/reports/20261028-skew-sink-drift.md`.

## Merge Danger

**Door:** two-way

Additive history records only; rendering and payloads unchanged.

**Blast Radius:** small

Splitkey checkups on configs with table-identified sink keys write more history records; `skew-stats`/`skew-drift` sweeps now include sink tables.
