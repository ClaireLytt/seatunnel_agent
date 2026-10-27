for #21 (data skew) — follow-up to #142

## Summary

The orchestrator (chat entry) catches up with the skew line — routing, page pointers, and one security-consistency fix.

```diff
 orchestrator catalog (no-db toolbox, "file-path tools are filtered out")
-  _SKIP_TOOLS = {skew_check_file}            # skew_runtime_eventlog leaked through
+  _SKIP_TOOLS = {skew_check_file, skew_runtime_eventlog}   # reads server paths
 _PAGES
+  skew_drift / skew_runtime_history / skew_runtime_flink -> /dataskew

 keyword router
-  "漂移/drift" -> schema_drift only          # 「倾斜漂移」went to the DDL diff
+  skew_drift: 倾斜漂移/漂移/分片键/splitkey/基线/热点值  (outranks schema_drift)
+  skew_runtime_history: 拖尾/straggler/history server/...
+  skew_runtime_flink: flink
```

## Evidence

- **Before:** asking the chat entry about 「分片键的倾斜漂移」 suggested the DDL schema-drift tool; the new skew tools had no page pointer in no-key suggestions; a server-path file reader was callable from chat despite the catalog's stated filter.
  **After:** `tests/test_orchestrator.py` asserts the routing win, the /dataskew page mappings, and that `skew_runtime_eventlog` is filtered — orchestrator+toolbox suites 78 passed; full `pytest -q` -> **3516 passed, 1 skipped**; ruff clean; mypy Success (175 files).
- Batch report: `docs/reports/20261028-skew-orchestrator.md`.

## Merge Danger

**Door:** two-way

**Blast Radius:** small

Chat sessions that previously called `skew_runtime_eventlog` lose that tool (intended — it reads server-local paths); keyword suggestions shift for drift-flavored queries.
