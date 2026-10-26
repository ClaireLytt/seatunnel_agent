# PR 草稿(uiskill → main)

创建命令(或在 GitHub 页面用下面的标题/正文):

```
gh pr create --base main --head uiskill --title "<下方标题>" --body-file docs/reports/PR_DRAFT_uiskill.md
```

**Title**: Chat BI: security hardening and 16 feature batches (model watch, targets, cache, ops tooling)

---

Closes #35 follow-ups on the uiskill branch: a security audit plus sixteen verified feature batches for the Chat BI stack.

## Security & correctness
- Close the comma-join table-whitelist bypass (sqlglot AST first, comma-aware regex fallback); literal-aware trailing-comment handling in enforce_limit
- Alias-aware column masking (`SELECT user_phone AS p` masks too, AS-less aliases via sqlglot); webhook host whitelist (`T2S_WEBHOOK_ALLOW_HOSTS`); pinned + checksummed CJK font URL (the old URL was a silent 404)
- Fix weekly-pattern leakage into the forecast OLS trend (backfit to convergence) — model baselines were biased ~10% on strongly periodic series

## Analysis features
- `watch_mode=model`: anomaly alerts against the forecast 95% interval instead of fixed thresholds; alert memory (one card per incident + recovery card); freshness probes kill fake -100% alerts from lagging pipelines
- Metric targets (`targets: {month: ...}`) + `metric_target_progress` (attainment & projection); `correlate_metrics` (Pearson + lead/lag scan); `t2s-sub backtest` replays alert rules over history
- Digest subscription (one morning card across metrics), freshness subscription, caliber-change tracing in `metrics validate`

## Cost & operations
- Semantic cache: an exact repeat of a verified question skips the LLM entirely (full validator path kept)
- `t2s-qlog-stats` (coverage/failures/slow/sources), `t2s-examples promote` (one-command curation), `metrics health` (red/yellow/green per-metric rollup), `t2s-doctor` (static drift check over examples/favorites/boards/subscriptions)
- REST + MCP facades for forecast/target/correlate; subscription cards honor the `lang` field (zh/en)

## Verification
- Full suite grew 3396 → 3451 passed (ruff/mypy clean every batch); real-browser smoke suite 16/16 PASS
- Per-batch reports under `docs/reports/2026102*-chatbi-*.md` with pasted check_workflow output (now mechanically enforced)
