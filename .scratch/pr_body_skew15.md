CI hardening round 2 — the pip stall's fourth recurrence (PRs #138, #141, #144, #148).

## Summary

The ui-smoke install step now retries itself inside the same job — a wedged runner no longer needs anyone (or any bot) to rerun the workflow.

```diff
 .github/workflows/uitest.yml
   - name: Install dependencies
     timeout-minutes: 6
+    id: deps
+    continue-on-error: true      # fail fast, don't fail the job yet
     ...
+  - name: Install dependencies (retry after a wedged first attempt)
+    if: steps.deps.outcome == 'failure'
+    timeout-minutes: 6           # cache warm -> normally <1 min
+    ...
```

No third-party action; `tests` is untouched (it has never wedged). `docs/pitfalls.md` entry updated — the manual cancel-and-rerun playbook is demoted to a last resort.

## Evidence

- **Before:** on PR #148 the stall cost a 6-minute auto-fail plus a scripted rerun (which itself landed on another slow runner) — ~15 minutes wall clock and two interventions.
  **After:** the second attempt runs immediately in the same job. Escalation history across the four incidents is recorded in `docs/pitfalls.md`.
- Workflows YAML-validated; repo intact (`ruff` clean, `pytest --collect-only` -> 3521 collected). This PR's own ui-smoke run exercises the changed steps.
- Batch report: `docs/reports/20261028-ci-install-retry.md`.

## Merge Danger

**Door:** two-way

**Blast Radius:** CI only

A genuine (non-transient) install breakage now surfaces one step later, after the retry also fails.
