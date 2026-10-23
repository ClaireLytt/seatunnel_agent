# Environment Doctor — Gradio → React Migration

**Label:** `ready-for-agent`

## Problem Statement

The Environment Doctor page (`/doctor`) is a Gradio page with no REST API (`api=None`). All other agent pages have been migrated to the React stack. This is the last Gradio-only page in the devops workspace without any HTTP surface.

## Solution

Create a REST API for the doctor agent, then migrate the page to a React workspace under `frontend/doctor/`, following the established pattern. Retire the old Gradio `ui.py`.

## User Stories

1. As a developer, I want the Environment Doctor page to match the engineering-paper design of all other agent pages.
2. As a developer, I want to type a symptom and click "Diagnose" to get a diagnosis with fix commands.
3. As a developer, I want to click "Full check-up" to get a deterministic report of ports, packages, LLM config, and logs without needing an LLM API key.
4. As a developer, I want to see loading and error states while diagnosis runs.
5. As a developer, I want to switch between English and Chinese.
6. As a developer, I want a "Clear" action to reset the form and report.
7. As a developer, I want the report rendered via the shared ReportView component.
8. As a developer, I want the page to work in light and dark mode.
9. As a developer, I want the page to be responsive on narrow screens.
10. As a maintainer, I want the old Gradio `ui.py` removed with all touchpoints cleaned up.

## Implementation Decisions

- **New REST API** (`doctor/api.py`):
  - `POST /api/doctor/diagnose` — accepts `{complaint, lang}`, calls `diagnose()` with settings if LLM is ready, returns `{reply, deterministic, elapsed_ms}`.
  - `GET /api/doctor/checkup?lang=zh` — calls `diagnose("checkup", settings=None)`, returns the deterministic check-up report.
  - `GET /api/doctor/health` — standard health endpoint.
- **Workspace:** `frontend/doctor/`, package name `@seatunnel/doctor`. Directory name equals manifest name.
- **Layout:** Two-column — left sidebar with symptom textarea (4 rows), "Diagnose" primary button, "Full check-up" secondary button, "Clear" ghost button. Right main area with ReportView.
- **Manifest update:** `external=True`, `render=""`, `api="seatunnel_agent.agents.devops.doctor.api:router"`.
- **i18n:** Migrate `_I18N` from `ui.py` to `i18n.ts`. Keys: title, subtitle, c_label, c_ph, run_btn, checkup_btn, clear_btn, report_ph, empty, running, home.

## Testing Decisions

- Test external behavior only.
- **Playwright page test:** `tests/test_doctor_page.py` — page load, "Full check-up" → report appears (deterministic, no LLM needed), clear resets.
- **i18n parity test:** `tests/test_doctor_i18n.py` — en/zh key parity + t() coverage.
- Prior art: `test_dep_check_page.py`, `test_dep_check_i18n.py`.
- The Playwright test uses "Full check-up" (deterministic) to avoid LLM dependency in CI.

## Out of Scope

- No new features.
- No changes to the doctor engine logic.
- No streaming — the diagnose call is one-shot.

## Further Notes

- The `diagnose()` function may be slow when using LLM; loading state should reflect this.
- The "Full check-up" button always works without an API key — this is the safe CI-testable path.
- Security: the engine already redacts credentials and refuses to read sensitive files; the API inherits this.
