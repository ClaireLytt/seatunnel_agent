# Spec: Slim down the tests/ module (dedupe shared test helpers)

Triage: `ready-for-agent`

## Problem Statement

As a maintainer of the test suite, every new agent page requires copy-pasting ~30 lines of i18n parity helpers (`_parse_locale`, `_resources`, `_workspace_sources`) into a new `test_<agent>_i18n.py`. Twenty files now carry byte-identical copies (differing only in the `I18N_TS`/`SRC` path constants and one comment). Smaller stub helpers (`_tool`/`_text` LLM-reply fakes, `_run_cli`) are also duplicated across 5 and 2 files respectively. When a helper needs a fix (e.g. the locale-parsing regex), it must be applied in 20 places, and copies have already begun to drift (comment-level drift today, logic drift tomorrow).

## Solution

Centralize the duplicated helpers in `tests/conftest.py` (or a small shared test-utils module), following the existing precedent: the per-page uvicorn fixture was already collapsed into the shared `make_page_url` factory in conftest. i18n test files then declare their two paths and get the parity checks from the shared implementation; agent-stub tests import the shared `_tool`/`_text` fakes.

## User Stories

1. As a test-suite maintainer, I want the i18n locale-parsing logic defined once, so that a regex fix lands everywhere at once.
2. As a test-suite maintainer, I want `_resources()` (en/zh block extraction) defined once, so that a change to the i18n.ts layout only requires one update.
3. As a test-suite maintainer, I want `_workspace_sources()` defined once, so that the workspace glob convention stays consistent across agents.
4. As an agent developer adding a new frontend workspace, I want to create its i18n parity test by declaring only `I18N_TS` and `SRC`, so that the new file is ~10 lines instead of ~60.
5. As a reviewer, I want i18n test files to contain only what is page-specific, so that diffs show real behavior changes rather than boilerplate.
6. As a test author faking LLM replies, I want shared `_tool`/`_text` reply builders, so that the Anthropic reply shape is encoded in one place.
7. As a test author of CLI tests, I want a shared `_run_cli` helper, so that CLI invocation conventions (argv, capture) stay uniform.
8. As a maintainer, I want the dedupe to preserve each file's existing test functions and assertions unchanged, so that coverage is provably identical before/after.
9. As a maintainer, I want the full pytest suite green after the change, so that the refactor is verified behavior-preserving.
10. As a maintainer, I want ruff/mypy to pass on the touched files, so that the repo's local verification loop stays intact.
11. As a future contributor, I want conftest comments to point at the shared factories (as the `make_page_url` comment already does), so that nobody reintroduces per-file copies.
12. As a maintainer, I want copies deleted, not shadowed, so that no dead duplicate helper remains importable.

## Implementation Decisions

- Follow the established conftest-factory pattern (`make_page_url` precedent): expose a factory, e.g. `make_i18n_checks(i18n_ts_path, src_dir)` or plain shared functions taking the paths as arguments; each `test_*_i18n.py` keeps only its path constants and its test functions calling the shared helpers.
- Prefer parameterized shared functions over a fixture, since the i18n tests are plain functions today; do not restructure test functions themselves.
- `_tool`/`_text` move to conftest as importable helpers; the 5 call sites switch to them.
- `_run_cli`: unify only if the two copies are behaviorally identical; otherwise leave and document why.
- No behavior change anywhere: same assertions, same test names, same collection count.
- The 9 ERA001 "commented-out code" ruff hits are explanatory comments, not dead code; they are intentionally kept (ERA is not in the project ruff config).
- Oversized-file splitting (e.g. the 4600-line data-comparison test file) is a separate decision and excluded here.

## Testing Decisions

- The test suite itself is the system under change; the success criterion is external behavior of the suite: identical collected test count (`pytest --collect-only -q`) and full `pytest` green before and after.
- Good test = asserts on parity/behavior (key sets match, every `t()` usage defined), never on helper internals; the dedupe must not add tests of the helpers themselves.
- Prior art: the `make_page_url` consolidation in tests/conftest.py, which this change mirrors.
- Verification per repo rules: `ruff check src tests`, `mypy`, `pytest`, plus before/after diff of collection counts reported in the batch report.

## Out of Scope

- Splitting oversized test files (>800 lines) — needs its own plan and approval.
- Removing the ERA001-flagged comments.
- Any change under `src/` or `frontend/`.
- The two different-signature `_write_eventlog` helpers (not duplicates).

## Further Notes

- Seam assumption (flagged for confirmation): the single seam is `tests/conftest.py` — the highest existing seam, already used for the page-test consolidation. No new module is introduced unless conftest grows unwieldy.
- Estimated reduction: ~550 lines (i18n trio) + ~55 lines (stubs/CLI helpers).
- This spec corresponds to 批次 1–2 of the slim-down investigation (2026-10-23).
