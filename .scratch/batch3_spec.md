## Problem Statement

The last two text2sql features — boards (dashboard pinning) and subscriptions (scheduled query + webhook push) — still live exclusively in the legacy Gradio page. Users must leave the React UI to manage them. Once these are migrated, the legacy Gradio page can be retired entirely, eliminating 2,226+ lines of dead code and three support files.

## Solution

Migrate boards and subscriptions into the React UI as batch 3, the final migration batch. Boards get a `#boards` hash view for browsing/rendering and a 📌 pin button in the chat result area. Subscriptions get a `#subscriptions` hash view with a CRUD table and run-now capability. After migration, the entire legacy Gradio page, its manifests, and its UI-only support files are deleted.

## User Stories

1. As a text2sql user, I want to pin a query result to a board by clicking 📌 in the result area, so that I can build dashboards from my queries.
2. As a text2sql user, I want to choose which board to pin to (or create a new one) via a popover, so that I can organize queries across multiple boards.
3. As a text2sql user, I want to navigate to `#boards` from the sidebar, so that I can browse my boards without leaving the React UI.
4. As a text2sql user, I want to see all boards in a list with name and item count, so that I can find the board I need.
5. As a text2sql user, I want to click a board to see its pinned queries, so that I can review my dashboard.
6. As a text2sql user, I want to render a board (re-execute all pinned queries), so that I can see up-to-date results.
7. As a text2sql user, I want render to require an active session, so that the queries execute against the correct datasource.
8. As a text2sql user, I want to delete a board, so that I can clean up boards I no longer need.
9. As a text2sql user, I want to navigate to `#subscriptions` from the sidebar, so that I can manage scheduled queries.
10. As a text2sql user, I want to see all subscriptions in a table with name, cron, source, enabled status, last run time, and last status, so that I can monitor them.
11. As a text2sql user, I want to create a subscription with name, cron schedule, metric or favorite source, and webhook URL, so that I receive automated query results.
12. As a text2sql user, I want to enable/disable a subscription with a toggle, so that I can pause without deleting.
13. As a text2sql user, I want to run a subscription manually (run-now), so that I can test it before waiting for the cron trigger.
14. As a text2sql user, I want to delete a subscription, so that I can remove ones I no longer need.
15. As a text2sql user, I want the pending-features box to disappear entirely after batch 3, so that I know everything is in the new UI.
16. As a developer, I want the legacy Gradio page fully retired (ui.py, ui_cards.py, i18n.py, ui_format.py, text2sql_legacy manifest deleted), so that there is one canonical UI to maintain.

## Implementation Decisions

- **Order within batch:** Boards first (simpler CRUD + render), then subscriptions (complex: cron scheduler + webhook).
- **Boards endpoints** (new `api_boards.py` sub-router):
  - `GET /api/text2sql/boards` — list all boards
  - `POST /api/text2sql/boards` — create a board (name)
  - `DELETE /api/text2sql/boards/{id}` — delete a board
  - `POST /api/text2sql/boards/{id}/pin` — pin a query (title, sql, ds_type)
  - `GET /api/text2sql/boards/{id}/render` — re-execute all pinned queries via `render_board()`, requires session_id query param
- **Boards UI:**
  - `#boards` hash view: board list table, click to expand items, render button (disabled without session), delete button
  - ResultBlock gets a 📌 pin button (alongside 👍/👎), click opens a popover with board dropdown + "new board" input
  - Sidebar gains a 📋 entry linking to `#boards`
- **Subscriptions endpoints** (new `api_subscriptions.py` sub-router):
  - `GET /api/text2sql/subscriptions` — list all
  - `POST /api/text2sql/subscriptions` — create (name, cron, source_type, metric, favorite_id, ds_type, connection, database, webhook_url, lang)
  - `DELETE /api/text2sql/subscriptions/{id}` — delete
  - `POST /api/text2sql/subscriptions/{id}/run` — manual run-now
  - `PATCH /api/text2sql/subscriptions/{id}` — enable/disable toggle
- **Subscriptions UI:**
  - `#subscriptions` hash view: table with name/cron/source/enabled/last_run/status, enable/disable toggle, run-now button, delete button
  - Create form: name, cron, source_type radio (metric/favorite), metric or favorite dropdown, webhook URL
  - Basic mode only — `metric_watch` with threshold alerting deferred
- **Scheduler:** The daemon-thread cron scheduler is backend-only; it already runs independently of the UI. No migration needed.
- **Final cleanup commit:** After boards + subscriptions are migrated, delete ui.py (2,226 LOC), ui_cards.py, i18n.py, ui_format.py, and the `text2sql_legacy` manifest. Remove the pending-features box from App.tsx entirely.
- **i18n:** Add keys for boards and subscriptions views in both English and Chinese.

## Testing Decisions

- **Test seam:** HTTP endpoints via `TestClient` wrapping `FastAPI` + `router`, same pattern as all other text2sql API tests.
- **What makes a good test:** Test external behavior (HTTP request → response). For boards render, mock the executor to avoid real DB; for subscriptions run-now, mock the webhook call.
- **Modules to test:**
  - Boards: CRUD (create, list, delete), pin, render (with mocked executor)
  - Subscriptions: CRUD (create, list, delete), enable/disable, run-now (with mocked webhook)
- **Prior art:** `tests/test_t2s_favorites_api.py`, `tests/test_t2s_feedback_api.py`.

## Out of Scope

- `metric_watch` subscription mode (threshold alerting with DoD/WoW comparison) — deferred to a follow-up
- Board item reordering or removal (individual items)
- Subscription editing (only create/delete/enable-disable for now)
- Webhook configuration UI (channel setup for Feishu/DingTalk/WeCom/email)
- Board sharing or export

## Further Notes

- This is batch 3 (final) of the 3-batch migration plan (parent: #106).
- After this batch, the full migration is complete: the React SPA at `/text2sql` is the sole UI, the legacy Gradio page is deleted, and Candidate 3 from the architecture review is achieved.
- The cron scheduler continues running as a backend daemon thread — it was never part of the Gradio UI, just started alongside it. The `start_global_scheduler()` call will move to the app startup hook.
- BoardStore supports max 50 boards, 30 items per board. SubscriptionStore has no hard cap but the JSON file is bounded by the scheduler's tick interval.
