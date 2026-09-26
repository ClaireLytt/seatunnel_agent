"""Global UI language preference.

The language is chosen ONCE on the hub landing page, whose native select
writes an ``st-lang`` cookie.  Every agent page reads that cookie on load —
server-side via :func:`choice_from_request` inside its ``app.load`` callback
(which feeds the page's existing ``_switch_lang``), and client-side via
:data:`STAMP_JS`, which stamps ``<body data-st-lang>`` so the UI test agent
can verify the active language.  Pages no longer have their own dropdowns.
"""

from __future__ import annotations

import gradio as gr

COOKIE = "st-lang"

# app.load(fn=None, js=STAMP_JS): stamp the body for the UI test agent.
STAMP_JS = """
() => {
    const m = document.cookie.match(/(?:^|; )st-lang=(zh|en)/);
    document.body.dataset.stLang = m ? m[1] : 'en';
}
"""

# Shared 🏠 button behavior (top-right of every page).
HOME_JS = "() => { window.location.href = '/'; }"


def choice_from_request(request: gr.Request | None) -> str:
    """Cookie -> the "English"/"中文" choice the _switch_lang callbacks expect."""
    try:
        lang = (request.cookies or {}).get(COOKIE, "en") if request else "en"
    except Exception:  # noqa: BLE001 — never break page load over a cookie
        lang = "en"
    return "中文" if lang == "zh" else "English"
