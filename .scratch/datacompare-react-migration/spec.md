# Spec: Data Comparison page — React Migration

Labels: ready-for-agent
Branch: seatunnel-react-migration (user-confirmed: continue on the current branch)

## Problem Statement

The Data Comparison page is the largest remaining Gradio page (form-and-dashboard paradigm, ~95 controls, ~40 handlers). It renders inconsistently with the refactored React pages, its language switch is a monolithic handler updating ~110 outputs, and its connection state lives in a process-global holder — all symptoms of the legacy rendering path the project is retiring page by page.

## Solution

Migrate the Data Comparison page to a standalone React SPA following the established migration checklist and the uitest form→dashboard precedent, scaled up: a wide configuration sidebar (dual data-source connections, presets, option accordions, feature accordions, action rows) driving a results panel. Comparison logic, report persistence, scheduling and webhooks stay server-side behind a dedicated REST API; the legacy Gradio page is fully retired. Functionality is 1:1 — nothing added, nothing removed.

## User Stories

1. As a data engineer, I want to open the Data Comparison page at its existing route, so that bookmarks and hub navigation keep working.
2. As a data engineer, I want the page to use the shared engineering-paper design system, so that it looks and behaves like the other refactored pages (including dark mode).
3. As a data engineer, I want to configure and connect source A and source B independently (datasource type, host/port/db/user/password with type-appropriate field visibility), so that I can compare across heterogeneous databases.
4. As a data engineer, I want per-side connect status and table pickers populated from the live connection, so that I know both sides are ready before comparing.
5. As a data engineer, I want to save, load and delete connection presets (with environment tag), so that I don't re-type credentials for recurring comparisons.
6. As a data engineer, I want global options (WHERE filter, numeric threshold, key columns, column mapping, sampling strategy incl. stratified column, masking) and a one-click options reset, so that I control comparison semantics.
7. As a data engineer, I want the core comparison actions — schema, count, sample, aggregate — so that I can check specific dimensions quickly.
8. As a data engineer, I want compound actions — compare-all with progress feedback, batch count, profile, batch full — so that I can run broad comparisons in one click without double-trigger accidents.
9. As a data engineer, I want the feature accordions preserved 1:1 — incremental (watermark), quality rules, skew, checksum (incl. chunked), partition, custom aggregates, custom SQL (A/B), sync-config generation (+download with real passwords, diff-SQL), templates (save/load/delete/batch-run), schedule (interval start/stop, server-side), webhook (url, notify-on-fail), trends with alert rules, report-vs-report diff, lineage, multi-environment — so that no workflow I rely on disappears.
10. As a data engineer, I want results rendered in the results panel exactly as today (server-rendered comparison cards), so that the information content of every action is unchanged.
11. As a data engineer, I want to save a report, list past reports, reload one, and diff two reports, so that comparisons are auditable over time.
12. As a data engineer, I want CSV/Excel export and a standalone report view that opens in a new tab, so that I can share results outside the tool.
13. As a data engineer, I want the trend chart rendered as a theme-aware chart in the page, so that trend analysis works in both themes (replacing the matplotlib PNG).
14. As a Chinese- or English-speaking user, I want the full dictionary (~247 keys) available per my language cookie, so that the migration loses no localization.
15. As a concurrent user, I want my connections keyed to my own session rather than a process-global holder, so that two users comparing different databases don't clobber each other.
16. As a maintainer, I want the legacy Gradio page retired (module deleted, hub CSS classes now unique to this page removed, UI-test engine references updated, hardcoded test lists fixed), so that one implementation remains.
17. As a maintainer, I want a Playwright page test replacing the page's YAML case coverage, so that browser regressions are caught in CI.
18. As a maintainer, I want before/after screenshots and a batch report, so that the migration is reviewable per project rules.

## Implementation Decisions

- Full migration to a new React workspace cloned from the uitest skeleton; uitest form→dashboard is the layout precedent, scaled to a wide sidebar + results panel. Engineering-paper theme only; no blue/purple, no gradients.
- Results rendering strategy (user-confirmed): the existing card-rendering module becomes pure functions invoked by the REST layer; endpoints return server-rendered HTML fragments that the React results panel displays in a controlled container. Card componentization is a possible later spec, not this one. Card CSS moves into the workspace (or a scoped stylesheet served with the page).
- Trend chart (user-confirmed by default): recharts with theme tokens, replacing matplotlib; the trend endpoint returns chart data, not an image.
- Comparison logic modules (comparator, chunked, models, presets store, templates store, report helpers) are not modified — a REST layer (~22-26 endpoints) is added over them: per-side connect (reusing the text2sql executor utilities), the comparison actions, presets CRUD, templates CRUD + batch run, reports (save/list/load/diff/trend-data/export CSV/Excel/standalone HTML), sync-config + diff-SQL generation, lineage, schedule start/stop/status, with webhook posting staying server-side.
- Connection state moves from the process-global holder to a server-side per-session connection registry (session/connection IDs issued by the API); schedule timers remain server-side keyed the same way.
- Long-running compound actions (compare-all, batch full) report progress — via the shared SSE helper (precedent: chat streaming) or polling; implementer picks the simpler one that preserves today's progress feedback.
- i18n dictionary ported verbatim to i18next (both locales), initialized from the language cookie; the monolithic language-switch handler disappears.
- The page keeps the Tab-fills-placeholder behavior currently borrowed from the text2sql resources script, reimplemented or imported equivalently in the workspace.
- Manifest flips to the external static mount; router mounted unconditionally after hub launch (manifest api left empty), matching all prior migrations.
- Retirement per the migration checklist: delete the UI modules (ui, ui_cards only if fully absorbed — any function still used by the REST layer moves to a non-Gradio module first), prune hub CSS classes that become unreferenced after this page leaves (verified by grep, not by list), update UI-test engine references and YAML cases that target the page, fix hardcoded test enumerations, keep the language-cookie bridge intact.
- Work proceeds in review-sized batches on the current integration branch (user-confirmed), each batch running the project verification commands and committing separately.

## Testing Decisions

- Good tests assert external behavior: HTTP contracts and what a real browser shows — never Gradio internals or React internals.
- Seams (both pre-existing in the repo):
  1. The HTTP API seam — the new router tested in-process: connect contract (success/failure, per-side), a representative comparison action against temp SQLite sources, presets/templates CRUD round-trips, report save/list/load/diff, export produces valid CSV/Excel, schedule start/stop. The comparator's own unit tests already cover comparison semantics and are untouched.
  2. The real-browser seam — a Playwright page test with in-process uvicorn (precedent: the other React page tests), covering page load, connect flow against a fixture source, one comparison action rendering cards, and language/dark-mode smoke.
- Visual conventions (theme tokens, card styling) evidenced by before/after screenshots per project rules.
- Full local gate per project rules, including the uitest smoke suite and the workflow check script.

## Out of Scope

- Any new features, option changes, or behavior changes beyond 1:1 parity.
- Rewriting the comparison cards as React components (deferred to a future spec).
- Changes to comparator/chunked/presets/templates logic modules.
- Migrating any other Gradio page; changes to text2sql beyond consuming its existing executor utilities server-side.
- Shipping/pushing the branch (separate user decision).

## Further Notes

- The page is LLM-free (pure deterministic comparison); no agent/LLM wiring is involved.
- Biggest risks, called out during grilling: the process-global connection holder → per-session registry refactor, and keeping scheduler/webhook server-side semantics identical.
- The hub CSS classes shared with this page were deliberately kept during the seatunnel retirement; after this migration they become unreferenced and should be pruned (verify by grep at retirement time).
- Scale reference: ~4200 lines of UI code replaced; ~2000 lines of logic untouched.
- Fix-up pass (post ticket 09) notes:
  - Accepted presentational deviation (P4): TrendsCard merges the legacy
    figure's two subplots (mismatches / schema_changes) into one grouped
    recharts BarChart — same data and series labels.
  - Accepted for now (S3, ticket 10/11): App.tsx passes the same ~5-prop
    bundle (sessionId/tableA/tableB/options/onResult) to six cards;
    consolidation is deferred to the cleanup tickets.
  - Shared backend bases now live in data_comparison/deps.py
    (get_session_or_404 + SessionTablesRequest/OptionsRequest); input
    validation errors are uniformly 422.
  - ConnectionRegistry is capped (100, evict oldest idle; scheduled
    sessions protected); the scheduled tick shares the compound
    per-session running guard (skips with last_error="busy").
  - Tab-fills-placeholder reimplemented as a React document-level hook
    (frontend/datacompare/src/tabFill.ts).
