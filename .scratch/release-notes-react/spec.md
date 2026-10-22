# Release Notes — Gradio → React Migration

**Label:** `ready-for-agent`

## Problem Statement

The Release Notes page (`/release`) is still a Gradio page while all other agent pages have been migrated to the React + Vite + Tailwind stack. This creates visual inconsistency and maintenance burden.

## Solution

Migrate the Release Notes page from Gradio to a React workspace under `frontend/release_notes/`, following the same pattern as dep_check, config_lint, and other migrated pages. Retire the old Gradio `ui.py`.

## User Stories

1. As a developer, I want the Release Notes page to match the engineering-paper design of all other agent pages, so that the platform feels cohesive.
2. As a developer, I want to paste commit log text and click "Generate" to see grouped release notes with a semver bump suggestion.
3. As a developer, I want to click "Load from repo" to auto-populate the commit log from the server's git history.
4. As a developer, I want to enter a current version so the semver suggestion is based on it.
5. As a developer, I want to toggle LLM polish to optionally refine the generated notes.
6. As a developer, I want to switch between English and Chinese.
7. As a developer, I want to see loading and error states while the generation runs.
8. As a developer, I want a "Clear" action to reset the form.
9. As a developer, I want the report rendered via the shared ReportView component.
10. As a developer, I want the page to work in light and dark mode.
11. As a developer, I want the page to be responsive on narrow screens.
12. As a maintainer, I want the old Gradio `ui.py` removed with all touchpoints cleaned up.

## Implementation Decisions

- **Workspace:** `frontend/release_notes/`, package `@seatunnel/release-notes`. Directory name equals manifest name (`release_notes`).
- **Shared infra:** PageHeader, Card, ReportView, shared Tailwind preset, Vite base config, shared CSS class constants.
- **Layout:** Two-column — left sidebar with commit log textarea, "Load from repo" button, version input, LLM polish checkbox, "Generate" primary button, "Clear" ghost button. Right main area with ReportView.
- **Backend additions:**
  - `GET /api/release/git-log` — calls `collect_git_log(".")` and returns the log text.
  - `POST /api/release/notes` — add optional `polish: bool` field to `NotesRequest`; when true, call `polish_markdown` on the result before returning.
- **i18n:** Migrate `_I18N` from `ui.py` to `i18n.ts`. Keys: title, subtitle, log_label, log_ph, repo_btn, version_label, polish_label, gen_btn, clear_btn, report_ph, empty_log, running, home.
- **Manifest update:** `external=True`, `render=""`.
- **Gradio retirement:** Delete `ui.py`, remove REL1 uitest case from `devops.yaml`, keep backend-only i18n keys in `report.py`.

## Testing Decisions

- Test external behavior only — does the page render, does Generate produce a report, does language toggle work.
- **Playwright page test:** `tests/test_release_notes_page.py` — page load, paste log + generate → report, clear resets, language toggle.
- **i18n parity test:** `tests/test_release_notes_i18n.py` — parse `i18n.ts`, verify en/zh key parity and t() coverage.
- Prior art: `test_dep_check_page.py`, `test_dep_check_i18n.py` (just written), `test_uitest_page.py`.
- Existing backend tests for release_notes core/api remain unchanged.

## Out of Scope

- No new features beyond what the current Gradio page offers.
- No changes to release_notes backend logic (core.py, report.py).
- No changes to the CLI.

## Further Notes

- The `polish_markdown` function requires an LLM API key; the checkbox should indicate this in its label.
- The `collect_git_log` call may be slow on large repos; the loading state should reflect this.
