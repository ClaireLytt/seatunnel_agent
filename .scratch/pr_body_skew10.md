CI hardening — no issue; born from two incidents on this repo's own PRs (#138, #141).

## Summary

The twice-seen pip stall on ui-smoke runners now fails fast and self-heals.

```diff
 .github/workflows/{uitest,tests}.yml
   - name: Install dependencies
+    timeout-minutes: 6          # was: stall ate the 20-minute job budget
+    env:
+      PIP_DEFAULT_TIMEOUT: "60" # pip survives transient network hiccups
+      PIP_RETRIES: "3"
```

Plus a `docs/pitfalls.md` entry (problem / root cause / mechanical fix / the manual cancel-then-rerun playbook), per the repo's "recurring (>=2) mistakes must be recorded" rule.

## Evidence

- **Before:** PR #138 and #141 each had ui-smoke wedged in `Install dependencies` (normally <1 min) for 6-9 minutes until manually cancelled and rerun — both reruns passed immediately.
  **After:** the same stall fails at 6 minutes and transient hiccups are retried by pip itself. Workflows YAML-validated; repo intact (`ruff` clean, `pytest --collect-only` -> 3517 collected). This PR's own CI run exercises the changed steps.
- Batch report: `docs/reports/20261028-ci-install-hardening.md`.

## Merge Danger

**Door:** two-way

**Blast Radius:** CI only

A genuinely slow (not stalled) install over 6 minutes would now fail the step; historical cached installs run well under 1 minute.
