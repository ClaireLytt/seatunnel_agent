for #21 (data skew) — follow-up to #136

## Summary

The runtime diagnosis now bridges into the split-key line: a skewed stage that names a table ends the report with something actionable about *that table*, instead of generic AQE advice only.

```diff
 diagnose_and_log (CLI / REST / MCP / page, shared tail)
   render runtime section
   re-check line vs previous diagnosis
+  for each implicated table (max 3, deterministic extraction):
+    patrol history exists  -> inline that table's drift verdict
+    no history             -> exact `skew-splitkey` pointer
+  all-ok diagnosis         -> no tail
```

Extraction is deterministic only — Flink `Source:/Sink: <table>` vertex names and Spark mapped SQL (`insert ... table X`, `from X`); an opaque vertex name yields nothing rather than a guess.

## Evidence

- **Before:** a confirmed straggler on `Source: ods.orders` ended with AQE parameters and "paste the SQL into static analysis" — the operator had to connect it to the split-key tooling by hand.
  **After:** the same report ends with `ods.orders`' drift-vs-baseline verdict (history present) or the exact `seatunnel-agent skew-splitkey` command (history absent). `tests/test_data_skew.py` 206 -> 208 passed; full `pytest -q` -> **3512 passed, 1 skipped**; ruff clean; mypy Success (175 files).
- Batch report: `docs/reports/20261028-skew-runtime-bridge.md`.

## Merge Danger

**Door:** two-way

Pure report-text addition behind the existing shared tail; no schema, endpoint or payload changes.

**Blast Radius:** minimal

Consumers that string-match runtime report text may see extra trailing lines on skewed runs.
