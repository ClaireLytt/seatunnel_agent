Task close-out — one consistency crumb.

## Summary

```diff
 .github/workflows/lint.yml (secretscan job)
-      - uses: actions/setup-python@v5   # survived the dependabot bump (#132)
+      - uses: actions/setup-python@v6   # all five lint jobs now agree
```

## Evidence

- `grep -c setup-python@v6 lint.yml` -> 5 (was 4 + one v5). YAML validated; repo intact (`ruff` clean, `pytest --collect-only` -> 3521 collected); this PR's own CI exercises the job.
- Batch report: `docs/reports/20261028-ci-setup-python-v6.md` — which also records that the task (issue #21 and its quality/CI offshoots, 16 merged PRs) has no further positive-value items; the only external dependency is upstream Zeta per-task metrics.

## Merge Danger

**Door:** two-way

**Blast Radius:** one CI job's action version
