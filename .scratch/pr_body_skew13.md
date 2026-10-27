for #21 (data skew) — follow-up to #146, closing the line

## Summary

The detector benchmark corpus gains a dialect dimension.

```diff
 examples/skew_bench/cases.yaml      23 -> 27 cases
+  mc-mapjoin-hint-clean   (maxcompute: /*+ MAPJOIN */ suppresses DS013
+                           like spark's BROADCAST)
+  mc-count-distinct       (maxcompute)
+  hive-dynamic-partition  (hive)
+  hive-null-key-outer-join (hive)
 guard test
+  asserts all three dialects are exercised, incl. the native-hint case
```

## Evidence

- Live run: `27 cases · precision 1.000 · recall 1.000 · F1 1.000 (gate 1.000)`; full `pytest -q` -> **3520 passed, 1 skipped**; ruff clean; mypy Success (175 files).
- Batch report: `docs/reports/20261028-skew-bench-dialects.md`.

## Merge Danger

**Door:** two-way

**Blast Radius:** none beyond the corpus — detector behavior untouched; the dialect branches are now under whole-corpus regression.
