# Dependency Health — Gradio → React Migration

**Label:** `ready-for-agent`

## Problem Statement

The Dependency Health page (`/depcheck`) is the last remaining Gradio page in the devops workspace. It uses `gradio.Blocks` for its UI while every other agent page has been migrated to the React + Vite + Tailwind stack with the shared engineering-paper design system. This creates visual inconsistency, duplicated styling infrastructure (Gradio CSS overrides vs Tailwind tokens), and makes the page harder to maintain alongside the rest of the frontend.

## Solution

Migrate the Dependency Health page from Gradio to a standalone React workspace under `frontend/dep_check/`, following the exact same patterns established by config_lint, schema_drift, and other migrated pages. Retire the old Gradio `ui.py`. The backend API (`POST /api/depcheck/check`, `GET /api/depcheck/health`) remains unchanged.

## User Stories

1. As a developer, I want the Dependency Health page to have the same look and feel as all other agent pages, so that the platform feels cohesive.
2. As a developer, I want to paste pyproject.toml or requirements.txt content and click "Analyze" to see the health report, so that I can check dependency status.
3. As a developer, I want to click "Check this project" to run the check against the server's own environment, so that I don't need to paste anything.
4. As a developer, I want to switch between English and Chinese, so that I can read the report in my preferred language.
5. As a developer, I want the page to show a loading state while the check is running, so that I know the system is working.
6. As a developer, I want to see error messages when my input is invalid (empty text, malformed TOML), so that I can correct it.
7. As a developer, I want the report rendered as styled Markdown with the same `ReportView` component used elsewhere, so that reports look consistent across pages.
8. As a developer, I want the page to work in both light and dark mode via the engineering-paper theme, so that it respects my system preference.
9. As a developer, I want a "Clear" action to reset the form and report, so that I can start fresh.
10. As a developer, I want the page to be responsive (sidebar stacks above main on narrow screens), so that it works on smaller viewports.
11. As a maintainer, I want the old Gradio `ui.py` removed and all its touchpoints cleaned up (hub CSS, uitest catalog, test hardcodes), so that there is no dead code.

## Implementation Decisions

- **Workspace:** New Vite + React 18 + TypeScript workspace at `frontend/dep_check/`. Package name `@seatunnel/dep-check`. Directory name equals manifest name (`dep_check`) per migration guide rule.
- **Shared infrastructure:** Import `PageHeader`, `Card`, `ReportView` from `@shared/components`. Use `btnPrimary`, `btnGhost`, `fieldCls`, `textareaCls`, `labelCls` from `@shared/constants`. Use shared Tailwind preset and Vite base config.
- **Layout:** Two-column — left sidebar (`lg:w-[420px]`) with textarea + two buttons; right main area (`flex-1`) with report output. Stacks vertically on mobile.
- **API wiring:** Plain `fetch` POST to `/api/depcheck/check` (synchronous JSON response, no SSE needed). The "Check this project" button uses the same endpoint but with empty text fields (the backend's `collect_from_path` is Python-side only; this button will need a new thin endpoint or be dropped — see Testing Decisions).
- **"Check this project" button:** The current Gradio UI calls `collect_from_path(".")` server-side. The REST API does not expose this. Decision: add a `GET /api/depcheck/check-self` endpoint that calls `collect_from_path(".") → check → render_markdown` and returns the same `CheckResponse` shape. This is a minimal backend addition.
- **i18n:** Migrate the `_I18N` dictionary from `ui.py` to `frontend/dep_check/src/i18n.ts` using i18next. Language initialized from `st-lang` cookie via `@shared/lang.ts`.
- **Manifest update:** Set `external=True`, `render=""` so the hub serves the React dist. Keep `api=` pointing to the existing router.
- **Gradio retirement touchpoints** (per `docs/react_migration.md` §6–12):
  - Delete `dep_check/ui.py`; keep backend-only i18n keys used by `report.py`.
  - Remove dep_check entries from `hub/css.py`.
  - Update `ui_testing/catalog.py` (AGENT_ROUTES, AGENT_LABELS).
  - Remove/update uitest cases referencing `/depcheck`.
  - Update `tests/test_registry.py` `_DATA_API_NAMES` if needed.

## Testing Decisions

- **Good tests:** Test external behavior (does the page render, does clicking Analyze produce a report, does language switch work) — not implementation details (internal state, component hierarchy).
- **Playwright page test:** `tests/test_dep_check_page.py` following the in-process uvicorn pattern from `test_uitest_page.py`. Covers: page load, paste text + analyze → report appears, clear resets, language toggle, error on empty input.
- **i18n parity test:** `tests/test_dep_check_i18n.py` following the pattern from `test_seatunnel_i18n.py` / `test_datacompare_i18n.py` — parse `i18n.ts` and verify all keys present in both en/zh.
- **Existing backend tests** for `dep_check` core/api remain unchanged — this is a UI-only migration.
- **Verification:** ruff / mypy / pytest / Playwright page test / uitest smoke / `check_workflow.py`.

## Out of Scope

- No new features (streaming, file upload, richer visualization).
- No changes to the dep_check backend logic (`core.py`, `report.py`).
- No changes to the CLI (`seatunnel-agent depcheck`).
- No changes to other agent pages.

## Further Notes

- The `check-self` endpoint is the only backend addition; it is a thin wrapper around existing functions.
- Follow `docs/react_migration.md` touchpoint checklist strictly to avoid dead code.
- After building (`seatunnel-agent ui --build`), verify the page at `/depcheck` looks correct in both light/dark mode and en/zh before retiring the Gradio version.
