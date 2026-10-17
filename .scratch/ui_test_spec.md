## Problem Statement

The text2sql React UI has 7 views but only 3 (chat, #schema, #history) have Playwright browser tests. The remaining 4 views (#favorites, #metrics, #boards, #subscriptions) have API-level tests but zero browser-level verification. Additionally, the YAML-based UI testing suite still points to the deleted `/text2sql-legacy` routes.

## Solution

Add Playwright smoke tests for the 4 uncovered React views and delete the obsolete YAML test cases that target `/text2sql-legacy`.

## User Stories

1. As a developer, I want Playwright tests for #favorites, so that I know the favorites list renders and search/rename/delete interactions work in a real browser.
2. As a developer, I want a Playwright test for #metrics, so that I know the metrics catalog table renders and the "Use" button navigates to chat with pre-filled input.
3. As a developer, I want a Playwright test for #boards, so that I know board creation and listing work in a real browser.
4. As a developer, I want a Playwright test for #subscriptions, so that I know the subscription table renders and the create form works.
5. As a developer, I want obsolete YAML UI test cases deleted, so that the test suite doesn't reference non-existent routes.

## Implementation Decisions

- **Seam**: Playwright browser → React SPA (same seam as existing `test_t2s_page.py`)
- **Fixture reuse**: All new tests reuse the existing server fixture pattern from `test_t2s_page.py` (FastAPI + uvicorn + built React dist)
- **Fake agent**: Reuse the FakeAgent pattern from existing tests for connect (no real DB needed for UI smoke tests, except favorites/boards which only need the API endpoints)
- **Test scope per view**:
  - `#favorites`: seed favorites via API, navigate, verify list renders, search filters, rename interaction
  - `#metrics`: navigate (no connect needed for API-level metrics endpoint), verify table renders, expand detail, click Use
  - `#boards`: create board via API, navigate, verify board appears in list
  - `#subscriptions`: navigate, verify table renders, open create form
- **YAML cleanup**: Delete all cases in `chatbi.yaml`, `aux_pages.yaml`, `scroll.yaml`, `extended.yaml` that reference `/text2sql-legacy`. Keep cases targeting other pages.
- **All tests marked `uitest`** (deselected by default pytest, run with `python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm`)

## Testing Decisions

- **Seam**: Browser → `/text2sql` React SPA (Playwright). Tests external rendering behavior, not API logic.
- **Prior art**: `tests/test_t2s_page.py` — exact same fixture pattern, same server setup, same FakeAgent.
- **What makes a good test here**: Navigate to the hash view, assert key DOM elements are present and interactive. No deep logic verification — that's the API tests' job.

## Out of Scope

- Testing metric_watch (deferred feature)
- Testing actual subscription execution or webhook delivery
- Testing board render with real SQL execution
- Rewriting YAML cases for React (Playwright tests replace them)

## Further Notes

- After this work, all 7 React views have browser-level coverage.
- The YAML suite will lose its text2sql-specific cases but retain all other pages (data compare, lineage, etc.).
