## Problem Statement

Text2SQL users who want to use SQL templates (preset analytical patterns like MoM, YoY, Top N) or browse the metrics semantic layer must leave the React UI and navigate to the legacy Gradio page. This breaks the workflow and blocks the eventual retirement of the legacy page.

## Solution

Migrate SQL templates and the metrics semantic layer browser into the React UI as batch 2 of the full migration. Templates appear as a quick-access button row above the chat input; the metrics catalog gets its own `#metrics` hash view with a table browser. After this batch, the legacy templates dropdown and metrics dropdown are removed, and the pending-features box shrinks to only subscriptions and boards.

## User Stories

1. As a text2sql user, I want to see SQL template buttons above the chat input, so that I can quickly start a common analytical query pattern.
2. As a text2sql user, I want to click a template button and have it pre-fill my chat input, so that I can edit and send the query without typing from scratch.
3. As a text2sql user, I want to see a tooltip on each template button showing its description, so that I understand what the pattern does before clicking.
4. As a text2sql user, I want templates to be visible even before connecting to a datasource, so that I can explore available patterns while deciding what to query.
5. As a text2sql user, I want to navigate to a `#metrics` view from the sidebar, so that I can browse the metrics catalog without leaving the new UI.
6. As a text2sql user, I want to see all defined metrics in a table with name, description, type, and source table, so that I can find the metric I need.
7. As a text2sql user, I want to click a metric row to expand its details (expression, dimensions, unit, owner), so that I understand its caliber before querying.
8. As a text2sql user, I want a "Use" button on each metric that jumps to chat with a pre-filled question, so that I can query the metric with one click.
9. As a text2sql user, I want the pre-filled question to include the first dimension when available (e.g. "Show GMV broken down by channel"), so that I get a useful default query.
10. As a text2sql user, I want the pending-features box to no longer list templates and metrics, so that I know they are available natively.
11. As a text2sql user, I want the legacy templates dropdown and metrics dropdown removed after migration, so that there is one canonical place for each feature.
12. As a text2sql user, I want the templates list to come from the server API, so that templates can be customized without rebuilding the frontend.

## Implementation Decisions

- **Templates endpoint:** `GET /api/text2sql/templates` returns the hardcoded `SQL_TEMPLATES` list from the templates module. Each template includes id, name (bilingual), description, and SQL pattern. Registered in a new `api_templates.py` sub-router, consistent with the Candidate 1 architecture.
- **Templates UI:** A row of compact buttons rendered above the ChatPanel input area. Each button shows the template name; hovering shows the description via `title` attribute. Clicking pre-fills the input with a hint string (e.g. "Use the Month-over-Month pattern to analyze "). Always visible, not gated by session state.
- **Metrics endpoint:** Reuse the existing `GET /api/text2sql/metrics` from `api_metrics.py`. No new backend work.
- **Metrics UI:** New `#metrics` hash view (parallel to `#schema`, `#history`, `#favorites`). Table layout with columns: name, description, type, table. Clicking a row expands to show expression/formula, dimensions, unit, owner. A "Use" button pre-fills the chat input and navigates to `#` (chat view). Pre-fill text follows legacy behavior: `"Show {display_name} broken down by {first_dimension}"` when dimensions exist, `"Show {display_name}"` otherwise.
- **Navigation:** Sidebar gains a 📊 entry linking to `#metrics`.
- **Pending box:** Remove "templates" and "metrics" entries; only "subscriptions" and "boards" remain.
- **Legacy cleanup:** Remove the templates dropdown, metrics dropdown, and their event handlers from the legacy Gradio page. Remove the corresponding manifest routes if they exist as standalone pages.
- **i18n:** Add keys for templates button labels, metrics view labels, and "Use" button in both English and Chinese.

## Testing Decisions

- **Test seam:** HTTP endpoints via `TestClient` wrapping `FastAPI` + `router`, same pattern as all other text2sql API tests.
- **What makes a good test:** Test external behavior (HTTP request → response JSON shape), not internal implementation. Templates are static data so the test just verifies the response structure.
- **Modules to test:**
  - `GET /api/text2sql/templates` — returns non-empty list with expected fields (id, name, description, pattern)
  - Metrics endpoint already tested elsewhere; no new backend tests needed for metrics
- **Prior art:** `tests/test_t2s_favorites_api.py`, `tests/test_t2s_schema_api.py`.

## Out of Scope

- Batch 3 features (subscriptions, boards/dashboards)
- User-defined custom templates (only the 8 hardcoded presets)
- Direct SQL parameter substitution in the templates UI (the LLM interprets the pattern)
- Metrics query execution from the `#metrics` view (use chat for that)
- Template editing or creation UI

## Further Notes

- This is batch 2 of a 3-batch migration plan (parent: #106).
- Batch ordering: ①favorites+feedback (done) → ②templates+metrics (this spec) → ③subscriptions+boards.
- After this batch, the pending-features box shows only 2 items (subscriptions, boards), and the legacy page loses two more feature sections.
- The templates module (`SQL_TEMPLATES`) contains 8 preset patterns: MoM, YoY, Top N, Ranked Groups, Daily Trend, Proportion, Moving Average, Cumulative Sum.
