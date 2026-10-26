# PR 草稿(uiskill → main)

创建命令(或在 GitHub 页面用下面的标题/正文):

```
gh pr create --base main --head uiskill --title "<下方标题>" --body-file docs/PR_DRAFT_uiskill.md
```

**Title**: Chat BI: security hardening, engine feature line and UI surfacing (model watch, targets, semantic cache, ops tooling)

---

Closes #35 follow-ups on the uiskill branch: a security audit plus 30+ verified batches across the Chat BI engine, its facades and the React UI.

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

## Analysis depth & correctness (second wave)
- Metric factor trees (`tree: [traffic, cvr, aov]`): exact log decomposition with auto-drilldown; named Chinese business periods (春节/2025国庆/上季度/近N天) resolve deterministically through the statutory calendar
- Alert memory (one card per incident + recovery card), alert history in qlog, `t2s-sub backtest` — whose test exposed and fixed a real forecast defect (weekly pattern leaking into the OLS trend, ~10% baseline bias)
- text2sql joined the mypy gate (107 → 174 gated files); its first run surfaced three latent runtime bugs (broken connection-preset import, REST run-now passing the wrong store, fpdf `uni` kwarg) — all fixed with regressions
- Pre-execution scan-cost advisories close the guard chain; `t2s-doctor`, `metrics health`, caliber-change tracing and `chatbi-demo` round out operations

## UI surfacing
- Subscription form grows to five source types (watch with mode/threshold, freshness, digest), a backtest button with inline results, a metric-health view, and the semantic cache reaching the chat UI with a zero-LLM badge
- Along the way: fixed the long-lived empty result-table bug (`preview_rows` vs `rows`) and a lifecycle test stub that had encoded a fixed bug's wrong signature

## Verification
- Full suite grew 3396 → 3470 passed (ruff/mypy clean every batch); Playwright page suite 21 cases and the real-browser smoke suite all green
- Per-batch reports under `docs/reports/2026102*-chatbi-*.md` with pasted check_workflow output (now mechanically enforced)
