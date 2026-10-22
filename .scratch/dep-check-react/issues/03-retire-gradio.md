# 03: Retire Gradio page + cleanup touchpoints

**What to build:** Remove the old Gradio `dep_check/ui.py` and clean up every reference per `docs/react_migration.md` §6–12:
- Delete `ui.py` (keep backend-only i18n keys in `report.py`)
- Remove dep_check CSS entries from `hub/css.py`
- Update `ui_testing/catalog.py` (AGENT_ROUTES, AGENT_LABELS)
- Remove uitest cases referencing `/depcheck`
- Update test hardcodes in `test_registry.py`

**Blocked by:** 02 (React page must work first)

**Status:** ready-for-agent

- [ ] `dep_check/ui.py` deleted
- [ ] No dep_check Gradio references in hub CSS
- [ ] uitest catalog updated
- [ ] uitest cases cleaned
- [ ] test_registry.py updated
- [ ] ruff + mypy + pytest pass
- [ ] No dead imports of gradio in dep_check package
