## Problem Statement

The text2sql legacy Gradio UI still contains code for features that have been fully migrated to the React UI (favorites, feedback, templates, metrics, schema browser, history). This dead code increases maintenance burden, confuses navigation (legacy routes still accessible), and blocks the eventual full retirement of the Gradio page.

## Solution

Remove all migrated features from the legacy Gradio page in a single cleanup pass. Delete the three standalone legacy pages (history, favorites, schema browser) and their manifests entirely. Strip the migrated feature sections (favorites, feedback, templates dropdown, metrics dropdown) from the main legacy page, leaving only the not-yet-migrated subscriptions and boards accordions.

## User Stories

1. As a developer, I want dead Gradio code removed, so that I don't accidentally modify legacy code instead of the React version.
2. As a text2sql user, I want `/history`, `/favorites`, and `/schema-browser` Gradio routes gone, so that I'm not confused by two different pages for the same feature.
3. As a developer, I want the legacy main page to only contain subscriptions and boards, so that I know exactly what remains to migrate in batch 3.
4. As a text2sql user, I want the legacy page to still work for subscriptions and boards, so that I can use those features until they are migrated.
5. As a developer, I want the manifest registry to reflect reality, so that the hub doesn't register routes for deleted pages.
6. As a developer, I want all existing tests to pass after cleanup, so that the removal is verified safe.

## Implementation Decisions

- **Single commit:** Combine batch 1 cleanup (#110) and batch 2 cleanup (#114) into one commit since the work is homogeneous (deleting Gradio code).
- **Delete standalone pages:** Remove `render_history_page`, `render_favorites_page`, `render_schema_browser_page` and their corresponding manifests (`t2s_history`, `t2s_favorites`, `t2s_schema_browser`).
- **Slim the main page:** From `render_text2sql_page`, remove: favorites save button + favorites accordion, thumbs up/down buttons + `_handle_feedback` handler, templates dropdown + preview + event handlers, metrics dropdown + preview + event handlers.
- **Preserve in main page:** Subscriptions accordion, boards accordion, datasource config sidebar, chatbot, chart rendering, new chat, i18n toggle — these stay until batch 3.
- **Legacy route stays:** The `/text2sql-legacy` route and `text2sql_legacy` manifest remain active to serve subscriptions + boards.
- **No React changes needed:** The pending-features box already shows only subscriptions and boards (done in batch 2 commit).

## Testing Decisions

- **Test seam:** The existing full test suite (`pytest -m "not uitest"`) is the verification surface. No new tests are needed for a deletion-only change.
- **What makes a good test here:** All 2957+ existing tests must continue to pass. Any test that was exercising deleted Gradio code should either be removed (if it only tested the deleted feature's Gradio wiring) or updated (if it tested shared logic through Gradio).
- **Prior art:** The batch 1 and batch 2 commits already adjusted test imports when code moved; this follows the same pattern.

## Out of Scope

- Batch 3 migration (subscriptions, boards)
- Full retirement of ui.py (requires batch 3 completion)
- Deletion of ui_cards.py, i18n.py, ui_format.py (still used by the remaining render_text2sql_page)
- Any React UI changes

## Further Notes

- After this cleanup, the legacy main page (`render_text2sql_page`) will be significantly shorter — roughly 1,000+ lines removed from the original 2,226.
- Once batch 3 migrates subscriptions and boards, the entire ui.py, ui_cards.py, i18n.py, and ui_format.py can be deleted along with the `text2sql_legacy` manifest (Candidate 3 from the architecture review).
- This cleanup closes both #110 and #114.
