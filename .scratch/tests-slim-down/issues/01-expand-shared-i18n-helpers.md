# 01: Expand: shared i18n parity helpers in conftest + pilot migration

**What to build:** A maintainer can fix the i18n locale-parsing logic in one place. The trio `_parse_locale` / `_resources` / `_workspace_sources` lives once in the shared test setup (conftest), parameterized by each workspace's i18n file path and source dir, following the existing `make_page_url` factory precedent. Two pilot i18n test files (ci_inspect and datacompare) are migrated to it, their local copies deleted, and the suite proves the change is behavior-preserving.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Shared helpers exist once, taking the i18n file path and source dir as parameters; no behavior change to parsing or globbing
- [ ] The two pilot files keep only their path constants and test functions; their helper copies are deleted
- [ ] `pytest --collect-only -q` count identical before/after; full `pytest` green; `ruff check src tests` and `mypy` pass
- [ ] A short conftest comment points future i18n test files at the shared helpers (mirroring the make_page_url note)
