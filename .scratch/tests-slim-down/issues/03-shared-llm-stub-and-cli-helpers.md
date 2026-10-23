# 03: Shared `_tool`/`_text` LLM-reply stubs and `_run_cli` helper

**What to build:** The fake LLM-reply builders (`_tool`, `_text`) are defined once in the shared test setup and used by the five agent-test files that currently carry their own copies, so a change to the reply shape is a one-edit fix. The two `_run_cli` copies are unified into one shared helper if behaviorally identical; if they differ, they stay separate with a one-line note saying why.

**Blocked by:** None (can start immediately).

**Status:** done (2026-10-23)

- [x] One shared definition of `_tool`/`_text`; the five files import it, local copies deleted
- [x] `_run_cli` unified or divergence documented
- [x] Test functions, names, and assertions unchanged; full `pytest` green; `ruff check src tests` and `mypy` pass
