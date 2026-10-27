# Spec: Skew Drift Detection (倾斜趋势漂移监测)

Labels: `ready-for-agent`
Tracker: local spec (per skill rule — no GitHub issue created)
Related: ClaireLytt/seatunnel_agent#21 (Data skew), branch `skew`

## Problem Statement

A data engineer runs the split-key check (`skew-splitkey`) as a patrol. Each run
measures the configured partition column's top-1 concentration, NDV and NULL
share and logs them, but every run is judged in isolation. A column whose skew
slowly worsens with business growth (a hot customer gaining share, NDV collapsing
after an upstream dedup change) passes every individual check until it finally
tips over a hard threshold and becomes a sync incident. Nobody is told "this key
is drifting" while the fix is still cheap.

## Solution

Reuse the existing patrol history (`logs/data_skew.jsonl`, mode=`splitkey`
records, which already carry `top1_pct` / `ndv` / `null_pct`). After enough
measurements of the same table exist, compare the latest measurement against a
baseline (median of the earlier ones). If top1 or NULL share rose, or NDV fell,
beyond thresholds, report a **drift** verdict: via a new `skew-drift` CLI
command, automatically after each `skew-splitkey` run, through the existing
patrol webhook, and as a trend hint on the Data Skew page.

## User Stories

1. As a data engineer, I want each split-key measurement compared to the table's historical baseline, so that slow skew growth is caught before it becomes an incident.
2. As a data engineer, I want a `skew-drift` CLI command that reads the existing history, so that I can audit drift without touching a live database.
3. As a data engineer, I want `skew-drift` with no table argument to sweep every table that has history, so that one patrol command covers the whole estate.
4. As a data engineer, I want the drift verdict printed at the end of a `skew-splitkey` run, so that I see "worse than last month" in the same report that measured it.
5. As a platform operator, I want a drift verdict to go to the existing patrol webhook, so that DingTalk/WeCom/Slack channels hear about drifting keys without a new integration.
6. As a data engineer, I want drift to require a minimum history depth, so that two noisy samples don't page anyone.
7. As a data engineer, I want the drift report to name the metric, baseline, current value and delta, so that I can judge severity at a glance.
8. As a data engineer, I want NDV collapse treated as drift even when top1 looks stable, so that upstream dedup/truncation accidents are caught.
9. As a data engineer, I want rising NULL share flagged, so that a split key silently filling with NULLs (all rows to one task) is caught early.
10. As a bilingual team member, I want drift output in zh/en following the agent's existing i18n convention, so that reports match the rest of the tool.
11. As a data engineer, I want `insufficient` clearly distinguished from `stable`, so that "no data" is never read as "no problem".
12. As a frontend user, I want the Data Skew page's trend area to show the drift verdict, so that the web UI and CLI agree.
13. As an operator, I want drift history itself logged to the JSONL history, so that `skew-stats` and the history panel reflect drift patrols.

## Implementation Decisions

- New module `drift` inside the Data Skew agent: pure functions over the
  history record dicts; no live SQL, no LLM. (Core already written in batch 1.)
- Baseline = median of all earlier measured records; latest record is the
  subject. Verdicts: `drift` / `stable` / `insufficient` (< 3 measured records).
- Thresholds as module constants: top1 +10 pp, null +5 pp, NDV −30 %.
  Documented, not configurable in v1 (keep simple).
- Input seam is `SkewHistory.splitkey_trend(table)` — already exists and is
  already consumed by the CLI trend line; drift adds no new storage or schema.
  Measured metrics were already persisted by `log_splitkey`.
- `skew-drift [TABLE]` CLI: with TABLE, one report; without, sweep
  `SkewHistory.splitkey_tables()`. `--webhook` posts via the existing
  `notify.post_webhook`. Exit code 0 always (advisory, like skew-stats).
- `skew-splitkey` appends a drift line after logging its measurement (it
  already prints a last-run comparison via `last_splitkey`; drift extends that
  to a baseline, same spot).
- i18n strings go into the agent's existing `i18n.dsk` table (zh/en pairs),
  matching the backend i18n key guard.
- REST: one read-only endpoint on the existing Data Skew router returning the
  drift result for a table (feeds the frontend trend card). No new router.
- Frontend: extend the existing trend display in `frontend/data_skew` with the
  drift verdict + per-metric deltas; no new page, no new workspace.

## Testing Decisions

- Good test = feed synthetic history records / a temp JSONL via
  `SEATUNNEL_SKEW_HISTORY_PATH` and assert on externally visible output
  (returned DriftResult fields, CLI stdout, webhook payload captured by
  monkeypatching `post_webhook`) — never on internal helpers.
- Unit-test the drift computation at the record-dict seam: insufficient
  history, stable, top1 drift, null drift, NDV drop, records missing metrics.
- CLI tests with click's CliRunner against a temp history file — prior art:
  `tests/test_data_skew.py` (`test_history_last_splitkey`, skew-stats and
  skew-splitkey CLI tests, webhook monkeypatch pattern).
- API test follows the existing Data Skew router test style.
- Frontend covered by the uitest smoke suite + screenshot (existing harness).

## Acceptance Criteria

1. `pytest tests/test_data_skew.py -q` tail shows `passed`, including new drift
   tests covering stories 1, 6, 7, 8, 9, 11 (insufficient vs stable asserted
   separately).
2. `ruff check src tests scripts` → `All checks passed!`; `mypy` → `Success` —
   repo gates intact.
3. `seatunnel-agent skew-drift <table>` against a seeded temp history prints
   metric, baseline, current, delta (story 2, 7); with no argument sweeps all
   tables (story 3). Evidence: command + output tail pasted in the batch report.
4. A `skew-splitkey` run (mock executor test) ends with the drift line
   (story 4); webhook test asserts the posted payload contains the drift
   verdict (story 5).
5. zh and en outputs both render via the i18n table; backend i18n key-guard
   test passes (story 10).
6. UI change verified in a real browser:
   `python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm`
   passes and the screenshot path is attached in the batch report (story 12).
7. `python scripts/check_workflow.py` tail `[PASS]` lines pasted in the batch
   report; batch report written under `docs/reports/` per TEMPLATE.md.
8. History records a drift patrol entry visible via `skew-stats` (story 13).

## Out of Scope

- Configurable thresholds / per-table threshold overrides.
- Drift on data_comparison's two-sided skew module (`data_comparison/skew.py`)
  — this spec covers the Data Skew agent's splitkey patrol only.
- Scheduling/cron; patrols remain externally triggered.
- Any change to the JSONL schema or retention/rotation behaviour.
- Forecasting future skew (only backward-looking baseline comparison).

## Further Notes

- Batch 1 (core `drift` module) exists on branch `skew`; batches 2 (CLI/webhook
  /splitkey hook) and 3 (REST + frontend + uitest) remain.
- Seam choice: the single highest existing seam is the history record list
  returned by `splitkey_trend` — everything else (CLI, REST, UI, webhook) is a
  thin consumer of `compute_drift`, keeping new seams at zero.
