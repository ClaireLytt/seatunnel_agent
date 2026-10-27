# 03: REST endpoint + Data Skew page trend card shows drift

**What to build:** The Data Skew web page's trend area shows the same drift
verdict the CLI reports: a read-only endpoint on the existing Data Skew router
returns the drift result for a table, and the frontend trend display renders
verdict plus per-metric deltas (bilingual, matching the page's i18n). Web UI
and CLI agree on every verdict.

**Blocked by:** 01 (Drift core).

**Status:** ready-for-agent

- [ ] Read-only drift endpoint on the existing Data Skew router; API test follows the router's existing test style (incl. `insufficient` and `drift` cases)
- [ ] Trend area renders verdict + deltas; no new page/workspace; no blue-purple colors
- [ ] `npm run lint` + `npm run build` for the data_skew workspace pass
- [ ] `python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm` passes; screenshot path attached in batch report
- [ ] `pytest` / `ruff` / `mypy` clean; batch report + check_workflow `[PASS]` lines
