"""Cross-page SQL hand-off over localStorage (the "bridge").

A sender page stores the SQL under a well-known key and opens the target
page; the target picks it up on load. Keys live here (Python side) and in
``frontend/shared/src/bridge.ts`` (React side) — ``tests/test_bridge.py``
keeps the two in sync.
"""

from __future__ import annotations

TRANSPILE_SQL_KEY = "st_transpile_sql"
DATASKEW_SQL_KEY = "st_dataskew_sql"

# Receiver side for Gradio pages: fill the textarea and fire an input event
# so gradio picks the value up. Remove only after successful delivery: if
# the textarea is not hydrated yet, the payload survives for a reload.
_PICKUP_JS = """
    () => setTimeout(() => {
        const v = localStorage.getItem('%(key)s');
        if (!v) return;
        const t = document.querySelector('%(selector)s');
        if (t) {
            localStorage.removeItem('%(key)s');
            t.value = v;
            t.dispatchEvent(new Event('input', {bubbles: true}));
        }
    }, 600)"""


def pickup_js(key: str, selector: str) -> str:
    """app.load(js=...) snippet that drains *key* into *selector*."""
    return _PICKUP_JS % {"key": key, "selector": selector}
