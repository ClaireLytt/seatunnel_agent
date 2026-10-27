for #21 (data skew) — follow-up to #137

## Summary

The page's drift card catches up with the CLI on hot-value identity.

```diff
 GET /api/skew/drift  (per table)
   verdict, samples, drifts[{metric, baseline, current, delta}]
+  hot_value: {prev, cur, changed}

 <DriftCard>
   verdict badge + per-metric deltas
+  amber "hot value changed: CN → US" line (drifted tables whose
+  top-1 value moved; hidden otherwise)
```

## Evidence

- **Before:** a drift whose skew moved to a different key said so in the CLI/webhook text, but the web card showed only the numbers.
  **After:** browser regression asserts the card renders `hot value changed: CN → US` from seeded history — `pytest -m uitest tests/test_dataskew_page.py` 22 passed; API test covers `changed: false` baseline and the CN→US case; full `pytest -q` -> **3512 passed, 1 skipped**; `npm lint/build data_skew` clean; uitest smoke 16/16 (`runs/20261028_013322/report.html`).
- Batch report: `docs/reports/20261028-skew-hot-value-ui.md`.

## Merge Danger

**Door:** two-way

Additive response field + one conditional card line.

**Blast Radius:** minimal

Strict validators of the /drift response schema would need to allow `hot_value`.
