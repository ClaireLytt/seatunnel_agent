# Spec: SeaTunnel Pipeline Builder — React Migration

Labels: ready-for-agent

## Problem Statement

The SeaTunnel Pipeline Builder page is the last chat-centric agent page still rendered as a server-side Gradio Blocks page, while the project's flagship pages (uitest, text2sql, sqlreview) have been rebuilt as standalone React SPAs on the shared "engineering-paper" design system. The Gradio page looks and behaves inconsistently with the refactored pages, is harder to style, and keeps a legacy rendering path alive that the project is actively retiring.

## Solution

Migrate the SeaTunnel Pipeline Builder to a standalone React SPA, following the established migration checklist and precedents. The page keeps its chat-session interaction model (sidebar with session history + streaming chat main area), adopts the shared engineering-paper theme and components, talks to the backend through a dedicated REST + SSE API, and the legacy Gradio page is fully retired. Functionality is 1:1 — nothing added, nothing removed.

## User Stories

1. As a data engineer, I want to open the SeaTunnel Pipeline Builder at its existing route, so that my bookmarks and the hub navigation keep working.
2. As a data engineer, I want the page to use the same visual language as the other refactored pages, so that the product feels like one coherent tool.
3. As a data engineer, I want to type a request and see the agent's response stream in token-by-token/event-by-event, so that I get feedback while long pipeline-generation runs.
4. As a data engineer, I want to stop a running generation, so that I don't wait on a request I no longer need.
5. As a data engineer, I want to upload a file into the conversation, so that the agent can work from my existing config or sample data.
6. As a data engineer, I want to run the built-in demo flow, so that I can see what the agent does without preparing my own input.
7. As a data engineer, I want to start a new chat, so that I can begin a fresh pipeline task without losing the old one.
8. As a data engineer, I want to see my previous sessions in a sidebar list, so that I can return to earlier work.
9. As a data engineer, I want to rename a session, so that my history stays organized.
10. As a data engineer, I want to delete a session, so that stale history doesn't pile up.
11. As a data engineer, I want to pick the agent mode, so that I control how the agent plans/executes.
12. As a data engineer, I want to set the config path, so that the agent reads/writes the right SeaTunnel config.
13. As a data engineer, I want to pick a pipeline template, so that I can start from a known-good baseline.
14. As a data engineer, I want to connect and see connection status, so that I know the agent can reach its backend before I ask for work.
15. As a data engineer, I want to export the current chat as a downloadable archive, so that I can share or archive the session.
16. As a data engineer, I want to collapse/expand the sidebar, so that I can maximize chat space on small screens.
17. As a Chinese- or English-speaking user, I want the page fully localized per my language cookie, so that the migration loses no i18n coverage.
18. As a user with the dark variant active, I want the page to render correctly in dark mode, so that the theme switch keeps working.
19. As a maintainer, I want the legacy Gradio page removed once the React page is live, so that there is a single implementation to maintain.
20. As a maintainer, I want the UI-test engine's routes, labels, and selectors updated for the new page, so that smoke suites keep passing.
21. As a maintainer, I want a Playwright page test for the new page, so that regressions are caught in CI without the retired Gradio case files.
22. As a maintainer, I want before/after screenshots in the migration report, so that the visual change is reviewable.

## Implementation Decisions

- Full migration to a new React workspace following the project's react-migration checklist and its three precedents; the uitest skeleton is the workspace starting point.
- Layout paradigm: chat-session page (sidebar + streaming chat), with text2sql as the closest structural precedent; visual style from the shared engineering-paper theme (Card, tailwind preset, theme tokens). No blue/purple or gradients, per project UI rules.
- Component strategy: chat components are implemented inside the new workspace, patterned on text2sql, NOT extracted into the shared package. text2sql is not touched. Abstraction is deferred until a third chat page exists.
- Backend: a dedicated FastAPI router namespace for the page, mounted unconditionally after hub launch (manifest `api` left empty to avoid double mounting). Endpoints cover: session CRUD (list/create/rename/delete/load), connect + status, mode/template/config-path metadata, file upload, demo run, chat message with streaming response, stop, and chat export (zip download).
- Streaming transport: SSE via the shared SSE helper; no WebSockets.
- Session persistence reuses the existing common history module (save/load/rename/delete) — no schema change.
- i18n: the Python i18n dict for this page is ported verbatim to i18next, initialized from the language cookie; after retirement only UI-chrome keys are pruned from the Python side.
- Manifest flips to external static mount (`external=True`, empty render), served from the built dist with the standard unbuilt-hint fallback.
- Retirement blast radius handled per checklist: delete the Gradio UI module, prune page CSS from the hub stylesheet, update the UI-test engine (ready routes, labels, result selectors, agent route/label catalog), remove the page's YAML case and scattered refs, fix hardcoded tests that enumerate pages/APIs.
- Work proceeds in 4 approved batches: (1) backend API + tests, (2) workspace skeleton + chat main area, (3) sidebar/sessions/i18n, (4) Gradio retirement + Playwright test + screenshots + report. Each batch runs the project verification commands and is committed separately.

## Testing Decisions

- Good tests exercise external behavior only: HTTP contracts of the new API and what a real browser sees on the page — never Gradio internals or React component internals.
- Seams (highest available, both pre-existing in the repo):
  1. The HTTP API seam — FastAPI router tested in-process (session CRUD round-trips, SSE event stream shape, export produces a valid zip), as the other migrated pages' API tests do.
  2. The real-browser seam — a Playwright page test with in-process uvicorn, modeled on the existing uitest page test, replacing the retired YAML case.
- No new seams introduced; the Gradio-era case file is replaced, not duplicated.
- Full local gate per project rules: ruff, mypy, pytest, frontend lint + build for the new workspace, uitest smoke suite (no-LLM), workflow check script.

## Out of Scope

- Any new features beyond 1:1 parity (no new chat capabilities, no new pipeline features).
- Extracting shared chat components into the shared package or modifying text2sql/sqlreview/uitest pages (except the mechanical UI-test engine updates required by retirement).
- Migrating any other Gradio page.
- Backend agent logic changes (tool execution, demo semantics, history storage format stay as-is).

## Further Notes

- The uitest page is a form/dashboard layout and is the *visual* reference only; the interaction model follows text2sql's chat paradigm — confirmed with the user during grilling.
- Demo mode's step-delay environment variable behavior must be preserved.
- Keep any cross-page localStorage bridges intact if a peer Gradio page still consumes them.
