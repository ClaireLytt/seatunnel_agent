for #21 (data skew) — follow-up to #135

## Summary

Second drift/runtime round: the patrol closes its own loops, and the runtime line gains the Flink engine.

```text
skew-splitkey patrol
  drift tail                                  # from #135
+ recovery card: a reported drift that settles back to stable
+   alerts once (console + webhook 'recovered'), from the patrol itself

skew-runtime
  eventlog | --history (Spark)                # from before
+ --flink <url> --app <jobId>                 # SeaTunnel on Flink:
+   per-subtask duration/read-bytes -> same max/median straggler test,
+   same re-check line. Zeta stays unsupported (its REST has only
+   job-level aggregates — documented in the guide).

drift report
+ hot-value identity: "hot value changed CN -> US" distinguishes
+   the-same-key-growing from the-skew-moved-to-a-different-key
+   (log_splitkey now persists top1_value; old records stay valid)
```

Facades: the Flink analyzer ships on all four entry points (CLI `skew-runtime --flink`, `POST /api/skew/runtime/flink`, MCP `skew_runtime_flink` incl. the no-db profile, and a "Flink diagnose" button on the page's runtime panel).

## Evidence

- Flink REST shape verified against the official docs before implementation (per-subtask `duration` + IOMetricsInfo `read-bytes`); Zeta's lack of per-task metrics likewise verified, so no speculative Zeta code.
- **Before:** splitkey-discovered drifts needed a separate `skew-drift` run to emit a recovery; runtime diagnosis was Spark-only; a drift alert could not say whether the hot key itself changed.
  **After:** `tests/test_data_skew.py` 202 -> 206 passed; browser suite 21 -> 22 passed (Flink button drives the report); full `pytest -q` -> **3510 passed, 1 skipped**; ruff clean; mypy Success (175 files); uitest smoke 16/16 (`runs/20261028_010626/report.html`).
- Batch reports: `docs/reports/20261028-skew-{splitkey-recovery,runtime-flink,flink-ui,hot-value}.md`.

## Merge Danger

**Door:** two-way

Additive: a new analyzer, endpoint, MCP tool and button; one new optional field in splitkey history records (`top1_value`, truncated to 120 chars) and recovery entries in webhook payloads.

**Blast Radius:** small

Webhook consumers see recovery cards they did not get before (and `recovered` in skew_drift payloads); strict payload validators would need to allow them.
