for #6, #62

## Summary

Complete Text2SQL React migration: all features migrated from the legacy Gradio page to the React SPA, architecture refactored (sub-routers, unified stores), and the legacy Gradio page retired (2,271 lines deleted). The React app at `/text2sql` is now the sole UI.

## Changes

### Batch 1: Favorites + Feedback (#107, #109)
- `GET/POST/PATCH/DELETE /api/text2sql/favorites` — full CRUD for saved SQL queries
- `POST /api/text2sql/feedback` — unified thumbs up/down endpoint (ExampleStore + FavoritesStore + qlog)
- React `#favorites` hash view with search, rename, delete
- 👍/👎 buttons in ResultBlock with mutual exclusion and visual feedback
- Sidebar ⭐ nav entry

### Batch 2: Templates + Metrics (#112, #113)
- `GET /api/text2sql/templates` — serves 8 preset analytical SQL patterns
- Template quick-access button row above ChatPanel input (click pre-fills)
- React `#metrics` hash view — catalog table with expand details + "Use" button
- Sidebar 📊 nav entry
- Pending-features box shrunk to subscriptions + boards

### Batch 3: Boards + Subscriptions (#117, #118)
- `GET/POST/DELETE /api/text2sql/boards`, `POST .../pin`, `GET .../render` — board CRUD with pin and render
- `GET/POST/DELETE/PATCH /api/text2sql/subscriptions`, `POST .../run` — subscription CRUD with enable/disable and run-now
- React `#boards` view with create, expand, render, delete
- React `#subscriptions` view with CRUD table, create form, enable/disable toggle, run-now
- Sidebar 📋 + 🔔 nav entries
- Pending-features box removed entirely

### Architecture: Sub-routers + Unified Stores
- `api.py` split into domain sub-routers: `api_favorites`, `api_feedback` (in favorites), `api_qlog`, `api_metrics`, `api_templates`, `api_boards`, `api_subscriptions` + `api_shared` for shared state
- `JsonFileStore` base class in `common/` — absorbs locked read/write/list/delete/cap boilerplate from FavoritesStore and ExampleStore
- `QueryLogger` refactored to wrap `common/JsonlLog` instead of reinventing it

### Legacy Retirement (#110, #114, #115, #119)
- Deleted `ui.py` (2,226 LOC), removed `text2sql_legacy` manifest
- Removed standalone legacy manifests for `/history`, `/favorites`, `/schema-browser`
- Legacy sidebar link removed from React app
- `ui_cards.py`, `i18n.py`, `ui_format.py` retained (used by agent tool result formatting)

## Testing
- `pytest -m "not uitest"`: **2971 passed**, 1 skipped
- `ruff check src tests`: all clean
- Frontend `vite build`: clean (1029 modules)
- New test files: `test_t2s_favorites_api.py` (7), `test_t2s_feedback_api.py` (3), `test_t2s_templates_api.py` (2), `test_t2s_boards_api.py` (7), `test_t2s_subscriptions_api.py` (7)
