# 04: Playwright page test + i18n parity test

**What to build:** Automated test coverage for the migrated page:
- `tests/test_dep_check_page.py` — Playwright test (in-process uvicorn) covering: page load, paste + analyze → report appears, check-self → report, clear resets, language toggle, error on empty input
- `tests/test_dep_check_i18n.py` — parse `i18n.ts`, verify all keys present in both en/zh

Final verification: ruff / mypy / pytest / uitest smoke / `check_workflow.py`.

**Blocked by:** 02 (page must exist to test)

**Status:** ready-for-agent

- [ ] `tests/test_dep_check_page.py` exists and passes
- [ ] `tests/test_dep_check_i18n.py` exists and passes
- [ ] Full suite: ruff / mypy / pytest green
- [ ] uitest smoke passes
- [ ] `check_workflow.py` passes
