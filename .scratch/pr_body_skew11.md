for #21 (data skew) — follow-up to #144

## Summary

`skew-drift` becomes pipeline-consumable, and the serialized drift shape gets a single source of truth.

```diff
 drift.py
+  drift_item_dict(result, lang)      # the one serialized item shape
 api.py GET /api/skew/drift
-  builds its item dicts inline
+  reuses drift_item_dict             # CLI and REST can no longer diverge
 skew-drift [TABLE]
+  --format/-F text|json              # {"items":[...]} identical to the REST
+                                     # endpoint; recovery entries flagged
+                                     # recovered: true; rich output silenced
```

`--fail`, `--webhook`, `-o` and history logging keep their exact semantics in json mode.

## Evidence

- **Before:** a pipeline wanting drift results as data had to scrape wrapped rich console text.
  **After:** `skew-drift orders -F json --fail` emits parseable items (table/verdict/drifts/hot_value/text) and exit code 1 on drift — asserted in `tests/test_data_skew.py` incl. REST-shape equality, the gate, and empty history -> `{"items": []}`. Full `pytest -q` -> **3517 passed, 1 skipped**; ruff clean; mypy Success (175 files). A test-helper gap (seeded history dropping `top1_value`) was found and fixed by the new test.
- Batch report: `docs/reports/20261028-skew-drift-json.md`.

## Merge Danger

**Door:** two-way

**Blast Radius:** minimal

Default text output unchanged; REST response bytes unchanged (same fields, now built by the shared helper).
