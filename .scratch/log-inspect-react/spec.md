# Log Inspect — Gradio → React Migration

**Label:** `ready-for-agent`

## Problem Statement

The Log Inspect page (`/loginspect`) is one of the last two Gradio pages. It needs migration to the React stack for consistency.

## Solution

Migrate to a React workspace under `frontend/log_inspect/`, following the established pattern. Add a missing LLM advice endpoint. Retire the Gradio `ui.py`.

## User Stories

1. As a developer, I want to enter a log directory path and click "Inspect directory" to see clustered ERROR/WARN events.
2. As a developer, I want to paste log text and click "Inspect text" to cluster inline logs.
3. As a developer, I want to toggle WARN inclusion and adjust the Top clusters count.
4. As a developer, I want to optionally request LLM advice on the clusters.
5. As a developer, I want to switch between en/zh.
6. As a developer, I want loading/error states and a Clear action.
7. As a developer, I want the page styled with the engineering-paper design.
8. As a maintainer, I want the old Gradio ui.py and its 6 uitest cases removed.

## Implementation Decisions

- **Backend addition:** `POST /api/loginspect/advice` — accepts `{scan_result, lang}`, calls `generate_advice()`, returns markdown advice text.
- **Workspace:** `frontend/log_inspect/`. Directory name = manifest name.
- **Layout:** Left sidebar with: directory input + "Inspect directory" (primary), collapsible "Inspect pasted text" section with textarea + button, WARN checkbox, Top clusters slider, "Clear" ghost button. Right main area with ReportView + collapsible "LLM advice" section.
- **Manifest:** `external=True`, `render=""`.
- **Retirement:** Delete `ui.py`, remove LGI1–LGI6 from `loginspect.yaml`, clean `ui_testing/page.py` references to `st-lgi`.

## Testing Decisions

- Playwright page test using directory scan against `examples/logs_demo`.
- i18n parity test.
- Prior art: `test_dep_check_page.py`, `test_dep_check_i18n.py`.

## Out of Scope

- No new features. No changes to clustering logic.
