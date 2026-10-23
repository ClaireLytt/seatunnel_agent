# 02: Migrate the remaining 18 i18n test files to the shared helpers

**What to build:** All twenty `test_*_i18n.py` files use the shared i18n parity helpers; a parsing fix now lands everywhere with one edit. Each file keeps only its path constants and its test functions; every remaining copy of `_parse_locale` / `_resources` / `_workspace_sources` is deleted (contract step — no shadowed duplicates remain).

**Blocked by:** 01 (Expand: shared i18n parity helpers in conftest + pilot migration).

**Status:** ready-for-agent

- [ ] Zero definitions of the helper trio remain outside the shared location (verifiable by grep)
- [ ] Test functions, names, and assertions in all 18 files unchanged
- [ ] `pytest --collect-only -q` count identical before/after; full `pytest` green; `ruff check src tests` and `mypy` pass
