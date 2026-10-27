for #21 (data skew) — follow-up to #139

## Summary

Two consistency touches on the drift line.

```diff
 <DriftCard>
-  open accordion -> click "Refresh drift" -> data
+  open accordion -> data (auto-fetch once; manual refresh kept)

 skew-drift [TABLE]
+  --output/-o <file>   # rendered lines (incl. recovery cards) saved
+                       # unwrapped, matching skew-splitkey/-runtime
```

## Evidence

- Browser regression now asserts the card populates on open with no refresh click — `pytest -m uitest tests/test_dataskew_page.py` 22 passed; CLI test asserts the `-o` file carries the full unwrapped text; full `pytest -q` -> **3514 passed, 1 skipped**; `npm lint/build data_skew` clean; uitest smoke 16/16 (`runs/20261028_020359/report.html`); ruff clean; mypy Success (175 files).
- Batch report: `docs/reports/20261028-skew-drift-polish.md`.

## Merge Danger

**Door:** two-way

UI convenience + an optional CLI flag; no schema or payload changes.

**Blast Radius:** minimal

Opening the drift accordion now issues one GET /api/skew/drift.
