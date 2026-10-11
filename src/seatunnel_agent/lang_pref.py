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

def _routes_js(workspace: str, fallback: list[str]) -> str:
    """Workspace page routes as a JS array literal — generated from the
    plugin registry so the back-button mapping can't drift when a plugin
    is added (the /docqa button once pointed at /data for exactly that)."""
    try:
        from .registry import discover
        routes = [m.route for m in discover() if m.workspace == workspace]
    except Exception:  # noqa: BLE001 — a broken plugin must not kill pages
        routes = fallback
    return "[" + ", ".join(f"'{r}'" for r in routes) + "]"


# app.load(fn=None, js=STAMP_JS): stamp the body for the UI test agent, and
# inject the workspace back-button next to the page's 🏠 (AI Platform pages
# go back to /ai, data agent pages to /data; the hub pages themselves have
# their own "← Platform home" link instead).
STAMP_JS = """
() => {
    const m = document.cookie.match(/(?:^|; )st-lang=(zh|en)/);
    const lang = m ? m[1] : 'en';
    document.body.dataset.stLang = lang;

    const AI_PAGES = __AI_PAGES__;
    const DEVOPS_PAGES = __DEVOPS_PAGES__;
    // engineering tools live on the landing page itself — 🏠 already returns
    const ENG_PAGES = ['/loginspect', '/uitest', '/mcp', '/settings'];
    const path = window.location.pathname.replace(/\\/+$/, '') || '/';
    if (path === '/' || path === '/data' || path === '/ai'
        || path === '/devops' || ENG_PAGES.includes(path)) return;
    let target, label;
    if (AI_PAGES.includes(path)) {
        target = '/ai';
        label = lang === 'zh' ? 'AI 平台' : 'AI Platform';
    } else if (DEVOPS_PAGES.includes(path)) {
        target = '/devops';
        label = lang === 'zh' ? 'DevOps' : 'DevOps';
    } else {
        target = '/data';
        label = lang === 'zh' ? '数据 Agent' : 'Data Agents';
    }
    let tries = 0;
    const timer = setInterval(() => {
        tries += 1;
        if (document.getElementById('st-ws-btn') || tries > 40) {
            clearInterval(timer);
            return;
        }
        const home = document.querySelector('.st-home-btn');
        if (!home) return;  // page without a home button: keep polling, then give up
        const btn = document.createElement('button');
        btn.id = 'st-ws-btn';
        btn.className = 'st-ws-btn';
        btn.textContent = '\\u21a9 ' + label;
        btn.title = target;
        btn.onclick = () => { window.location.href = target; };
        home.parentElement.insertBefore(btn, home);
        clearInterval(timer);
    }, 250);
}
"""

STAMP_JS = STAMP_JS.replace(
    "__AI_PAGES__", _routes_js("ai", ["/orchestrator", "/llmeval",
                                      "/promptlab", "/llmcost", "/docqa"]),
).replace(
    "__DEVOPS_PAGES__", _routes_js("devops", ["/secretscan", "/ciinspect",
                                              "/depcheck", "/release"]),
)

# Shared 🏠 button behavior (top-right of every page).
HOME_JS = "() => { window.location.href = '/'; }"


def choice_from_request(request: gr.Request | None) -> str:
    """Cookie -> the "English"/"中文" choice the _switch_lang callbacks expect."""
    try:
        lang = (request.cookies or {}).get(COOKIE, "en") if request else "en"
    except Exception:  # noqa: BLE001 — never break page load over a cookie
        lang = "en"
    return "中文" if lang == "zh" else "English"
