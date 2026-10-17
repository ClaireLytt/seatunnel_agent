## Parent

#106

## Problem Statement

After a text2sql query returns results, users have no way to give feedback (thumbs up/down) in the React UI. In the legacy Gradio page, thumbs up adds the question+SQL pair as a few-shot example (improving future suggestions) and saves it as a favorite; thumbs down removes the few-shot example and logs it. This feedback flywheel is a core mechanism for text2sql quality improvement and must migrate to the new UI.

## Solution

Add 👍/👎 buttons below each SQL result in the React ChatPanel, backed by a unified `POST /api/text2sql/feedback` endpoint that preserves the full legacy semantics: positive feedback adds a few-shot example + saves a favorite + logs to qlog; negative feedback removes the few-shot example + logs to qlog.

## User Stories

1. As a text2sql user, I want to click 👍 on a query result, so that the SQL is saved as a favorite and added as a few-shot example for better future suggestions.
2. As a text2sql user, I want to click 👎 on a query result, so that the bad few-shot example is removed and the system learns from my negative feedback.
3. As a text2sql user, I want to see the 👍/👎 buttons only on messages with SQL execution results, so that the feedback is contextually relevant.
4. As a text2sql user, I want the button to disable after I click it, so that I don't accidentally submit duplicate feedback.
5. As a text2sql user, I want visual confirmation after clicking (button state change + short text), so that I know my feedback was recorded.
6. As a text2sql user, I want 👍 and 👎 to be mutually exclusive, so that I can only give one type of feedback per result.
7. As a text2sql user, I want thumbs up to automatically name the favorite after my question, so that I don't have to type a name (I can rename later in #favorites).
8. As a text2sql user, I want my feedback to be logged in qlog with status "feedback_up" or "feedback_down", so that there is an audit trail.

## Implementation Decisions

- **Unified feedback endpoint:** `POST /api/text2sql/feedback` with body `{session_id, question, sql, positive}`.
- **Positive path (`positive=true`):**
  1. `ExampleStore.add(question, sql, tables, source="feedback")` — adds a verified few-shot example
  2. `FavoritesStore.save(question_as_name, sql, question, ds_type)` — saves as a favorite
  3. `runtime.logger.log(...)` with `status="feedback_up"` — audit trail
- **Negative path (`positive=false`):**
  1. `ExampleStore.remove_by_question(question)` — removes the bad example
  2. `runtime.logger.log(...)` with `status="feedback_down"` — audit trail
- **`ds_type` auto-derived:** The backend reads `agent.runtime.ds_type` from the session — the frontend does not pass it.
- **`session_id` required:** The endpoint needs an active session to access the agent's ExampleStore and runtime logger. The frontend has session context because ChatPanel is only rendered when connected.
- **Button placement:** Below each ResultBlock in ChatPanel (only on messages containing SQL execution results, not plain text answers).
- **Interaction states:** Idle → clicked (disabled + visual change). 👍 and 👎 are mutually exclusive — clicking one disables both. 👍 turns highlighted, 👎 turns red/accent colored. A short text appears beside the clicked button.
- **No feedback on history view:** Buttons only appear in the active ChatPanel, not in #history or #favorites views.
- **Tables extraction:** The backend calls `extract_tables(sql)` (from the validator module) to populate the ExampleStore entry, matching legacy behavior.

## Testing Decisions

- **Test seam:** HTTP endpoints via `TestClient` wrapping `FastAPI` + `router`, same pattern as `test_t2s_schema_api.py` and the new `test_t2s_favorites_api.py`.
- **What makes a good test:** Test external behavior (HTTP request → response + side effects on disk), not internal implementation details. Use temp files for both FavoritesStore and ExampleStore.
- **Modules to test:**
  - Feedback endpoint positive path: verify favorite created + example added + qlog entry
  - Feedback endpoint negative path: verify example removed + qlog entry
  - 404 on unknown session_id
- **Prior art:** `tests/test_t2s_favorites_api.py` (just created), `tests/test_t2s_schema_api.py`.

## Out of Scope

- Batch 2 features (templates, metrics semantic layer)
- Batch 3 features (subscriptions, boards/dashboards)
- Feedback on historical results (only active chat)
- Undo/retract feedback
- Feedback analytics dashboard

## Further Notes

- This is ticket 3 of 4 in the batch 1 migration plan (#106).
- The feedback endpoint reuses two existing stores (FavoritesStore, ExampleStore) and the existing qlog infrastructure — no new data models needed.
- After this ticket and ticket #108 (favorites manage) are done, ticket #110 (legacy cleanup) removes the corresponding Gradio code.
