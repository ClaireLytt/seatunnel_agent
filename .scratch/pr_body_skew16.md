CI hardening round 3 — close the last unguarded install steps.

## Summary

`uitest-nightly.yml`'s two install steps get the same wedged-pip treatment already proven on `uitest.yml` (#144, #149): 6-minute step timeout, pip retry env, and an in-place second attempt.

```diff
 .github/workflows/uitest-nightly.yml   (both jobs: smoke-llm + hive)
   - name: Install dependencies
+    timeout-minutes: 6
+    continue-on-error: true
+    env: {PIP_DEFAULT_TIMEOUT: "60", PIP_RETRIES: "3"}
+  - name: Install dependencies (retry after a wedged first attempt)
+    if: steps.deps*.outcome == 'failure'
```

Why it matters more here than on PR workflows: nightly runs unattended with a 90-minute job budget — a wedge previously meant a silently hung night.

## Evidence

- Four stall incidents on the same runner pool this week (PRs #138/#141/#144/#148), history in `docs/pitfalls.md` (file list updated).
- Workflows YAML-validated; repo intact (`ruff` clean, `pytest --collect-only` -> 3521 collected). Nightly is schedule-triggered, so the live proof lands on the next scheduled run.
- Batch report: `docs/reports/20261028-ci-nightly-retry.md`.

## Merge Danger

**Door:** two-way

**Blast Radius:** CI only (nightly workflows)
