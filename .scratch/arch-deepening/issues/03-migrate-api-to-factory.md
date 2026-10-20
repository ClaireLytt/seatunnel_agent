# 03: Migrate remaining api.py files to the router factory

**What to build:** All standard agents use the factory. Non-standard agents (schema_drift with dual-mode input, pii_scan with extra /rules endpoint) keep a thin custom api.py that extends the factory output. All API tests pass.

**Blocked by:** 02 (router factory).

**Status:** ready-for-agent

- [ ] All standard single-endpoint agents use `make_agent_router()`: dag_check, data_skew, sql_testgen, config_lint, config_migrate, sql_fmt, sql_transpile, data_comparison, sql_review, data_lineage, change_impact
- [ ] Non-standard agents (schema_drift, pii_scan, seatunnel) use factory where possible, extend with custom routes
- [ ] Each migrated api.py is ≤20 lines (config + any custom routes)
- [ ] All existing API and page tests pass
- [ ] `ruff check` and `mypy` pass
