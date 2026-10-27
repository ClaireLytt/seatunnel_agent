for #21 (data skew) — docs follow-up to #141

## Summary

README's Data Skew sections (EN + 中文) catch up with the shipped line; docs only, no code.

```diff
 ### Data Skew Analyzer Agent
   static rules + LLM rewrite + live probes + consistency   # unchanged
+  split-key checkup: --apply write-back, directory patrol + webhook,
+    sink-side keys, history-backed trends
+  skew drift: baseline verdicts, hot-value identity, deduplicated
+    alerts (first/escalation/recovery), --fail CI gate, drift card/MCP/REST
+  runtime diagnosis: Spark event log / History Server / Flink
+    per-subtask metrics, re-check line, bridge to the split-key line
+  link to docs/data_skew_guide.md
 ```bash
-  skew / skew-stats / skew-mcp                      # 3 examples
+  + skew-splitkey (apply / patrol+webhook), skew-drift --fail,
+  + skew-runtime (eventlog / --flink)               # 10 examples
 ```
```

## Evidence

- Docs-only diff (`README.md` + the batch report). Repo-intact checks per the docs rule: `ruff check src tests` -> All checks passed; `pytest --collect-only -q` -> 3516 collected.
- Batch report: `docs/reports/20261028-skew-readme.md`.

## Merge Danger

**Door:** two-way

**Blast Radius:** none (documentation text only)
