"""Gradio Web UI for SeaTunnel Agent.

Run with:  python -m seatunnel_agent.ui
Or:        seatunnel-agent ui
"""

from __future__ import annotations

import gradio as gr

from .hub_pages import (  # noqa: F401 — re-exported for back-compat
    _build_ai_hub_html,
    _build_data_hub_html,
    _build_devops_hub_html,
    _build_landing_html,
    _mount_hub,
)
from seatunnel_agent.agents.data.seatunnel.ui import (  # noqa: F401 — re-exported for back-compat
    EventCollector,
    _TOOL_EMOJI,
    _build_template_choices,
    _export_session,
    _format_events_as_chat,
    _normalize_chat,
    _render_seatunnel_page,
    _template_to_prompt,
)
from .ui_css import _CUSTOM_CSS  # noqa: F401 — re-exported for back-compat


# Drag-to-resize for the left sidebar: restores the saved width, appends a
# handle to .st-page-row (not inside .st-sidebar — sidebar_fix.js forces
# inline width on its direct div children) and drives --st-sidebar-w.
_SIDEBAR_RESIZE_JS = """
() => {
    if (window.__stSidebarResize) return;
    window.__stSidebarResize = true;
    const MIN = 180, MAX = 520, KEY = 'stSidebarW';
    try {
        const saved = parseInt(localStorage.getItem(KEY), 10);
        if (saved >= MIN && saved <= MAX) {
            document.documentElement.style.setProperty('--st-sidebar-w', saved + 'px');
        }
    } catch (e) {}
    let tries = 0;
    const init = () => {
        const row = document.querySelector('.st-page-row');
        const sb = row && row.querySelector('.st-sidebar');
        if (!row || !sb) {
            if (tries++ < 50) setTimeout(init, 200);
            return;
        }
        // The Data Comparison sidebar has its own CSS resize (720px wide);
        // the fixed-position handle would float mid-sidebar and swallow
        // clicks on anything underneath it.
        if (sb.classList.contains('st-dc-sidebar')) return;
        if (row.querySelector('.st-sidebar-resize')) return;
        const handle = document.createElement('span');
        handle.className = 'st-sidebar-resize';
        handle.title = 'Drag to resize sidebar';
        row.appendChild(handle);
        const syncVisible = () => {
            handle.style.display =
                getComputedStyle(sb).display === 'none' ? 'none' : '';
        };
        syncVisible();
        new MutationObserver(syncVisible)
            .observe(sb, {attributes: true, attributeFilter: ['style', 'class']});
        let startX = 0, startW = 0;
        const onMove = (e) => {
            const w = Math.min(MAX, Math.max(MIN, startW + e.clientX - startX));
            document.documentElement.style.setProperty('--st-sidebar-w', w + 'px');
        };
        const onUp = () => {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            handle.classList.remove('st-resizing');
            document.body.classList.remove('st-sidebar-dragging');
            try {
                const w = parseInt(
                    getComputedStyle(document.documentElement)
                        .getPropertyValue('--st-sidebar-w'), 10);
                if (w) localStorage.setItem(KEY, String(w));
            } catch (e) {}
        };
        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            startX = e.clientX;
            startW = sb.getBoundingClientRect().width;
            handle.classList.add('st-resizing');
            document.body.classList.add('st-sidebar-dragging');
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    };
    init();
}
"""


def create_ui() -> gr.Blocks:
    """Multipage app: hub landing page + one dedicated page per agent."""
    # UI-saved LLM settings override .env for this process (see /settings).
    from dotenv import load_dotenv
    load_dotenv()
    from .common import settings_store
    settings_store.apply_to_env()

    from seatunnel_agent.agents.data.text2sql.ui import render_text2sql_page, render_history_page, render_favorites_page, render_schema_browser_page
    from seatunnel_agent.agents.data.data_comparison.ui import render_data_comparison_page
    from seatunnel_agent.agents.data.sql_review.ui import render_sql_review_page
    from seatunnel_agent.agents.data.data_skew.ui import render_data_skew_page
    from seatunnel_agent.agents.data.mcp_toolbox.ui import render_mcp_page

    _hide_sub_nav_js = """
    () => {
        function hide() {
            document.querySelectorAll('nav a, .navigation a, a[href*="history"], a[href*="favorites"]').forEach(a => {
                const t = a.textContent.trim();
                const h = a.getAttribute('href') || '';
                if (t === 'Query History' || t === 'SQL Favorites'
                    || h.includes('/history') || h.includes('/favorites')) {
                    a.style.display = 'none';
                }
            });
        }
        hide();
        new MutationObserver(hide).observe(document.body, {childList: true, subtree: true});

        if (!document._tabFillReady) {
            document._tabFillReady = true;
            document.addEventListener('keydown', function(e) {
                if (e.key !== 'Tab') return;
                var el = e.target;
                if (el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA') return;
                if (el.value.trim() !== '' || !el.placeholder) return;
                e.preventDefault();
                var proto = el.tagName === 'TEXTAREA'
                    ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                setter.call(el, el.placeholder);
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            });
        }
    }
    """

    with gr.Blocks(
        title="SeaTunnel Agent",
        fill_height=True,
        fill_width=True,
    ) as app:
        _mount_hub(app, _build_landing_html)
        app.load(fn=None, js=_hide_sub_nav_js)

    with app.route("Data Agents", "/data"):
        _mount_hub(app, _build_data_hub_html)

    with app.route("AI Platform", "/ai"):
        _mount_hub(app, _build_ai_hub_html)

    with app.route("DevOps", "/devops"):
        _mount_hub(app, _build_devops_hub_html)

    with app.route("SeaTunnel", "/seatunnel"):
        _render_seatunnel_page(app)
        app.load(fn=None, js=_SIDEBAR_RESIZE_JS)

    with app.route("Text2SQL", "/text2sql"):
        render_text2sql_page(app)
        app.load(fn=None, js=_SIDEBAR_RESIZE_JS)

    with app.route("Query History", "/history"):
        render_history_page(app)

    with app.route("SQL Favorites", "/favorites"):
        render_favorites_page(app)

    with app.route("Schema Browser", "/schema-browser"):
        render_schema_browser_page(app)

    with app.route("Data Comparison", "/datacompare"):
        render_data_comparison_page(app)
        app.load(fn=None, js=_SIDEBAR_RESIZE_JS)

    with app.route("SQL Review", "/sqlreview"):
        render_sql_review_page(app)

    with app.route("Lineage", "/lineage"):
        from seatunnel_agent.agents.data.data_lineage.ui import render_lineage_page
        render_lineage_page(app)

    with app.route("SQL Transpile", "/transpile"):
        from seatunnel_agent.agents.data.sql_transpile.ui import render_sql_transpile_page
        render_sql_transpile_page(app)

    with app.route("Change Impact", "/impact"):
        from seatunnel_agent.agents.data.data_lineage.ui_impact import render_impact_page
        render_impact_page(app)

    with app.route("Config Migrate", "/migrate"):
        from seatunnel_agent.agents.data.config_migrate.ui import render_config_migrate_page
        render_config_migrate_page(app)

    with app.route("UI Testing", "/uitest"):
        from .ui_testing.gradio_page import render_uitest_page
        render_uitest_page(app)

    with app.route("Settings", "/settings"):
        from .settings_ui import render_settings_page
        render_settings_page(app)

    with app.route("Data Skew", "/dataskew"):
        render_data_skew_page(app)

    with app.route("PII Scan", "/pii"):
        from seatunnel_agent.agents.data.pii_scan.ui import render_pii_page
        render_pii_page(app)

    with app.route("Log Inspect", "/loginspect"):
        from seatunnel_agent.agents.data.log_inspect.ui import render_log_inspect_page
        render_log_inspect_page(app)

    with app.route("Schema Drift", "/schemadrift"):
        from seatunnel_agent.agents.data.schema_drift.ui import render_schema_drift_page
        render_schema_drift_page(app)

    with app.route("Test Data", "/testgen"):
        from seatunnel_agent.agents.data.sql_testgen.ui import render_sql_testgen_page
        render_sql_testgen_page(app)

    with app.route("Config Lint", "/conflint"):
        from seatunnel_agent.agents.data.config_lint.ui import render_config_lint_page
        render_config_lint_page(app)

    with app.route("DAG Check", "/dagcheck"):
        from seatunnel_agent.agents.data.dag_check.ui import render_dag_check_page
        render_dag_check_page(app)

    with app.route("Metric Diff", "/metricdiff"):
        from seatunnel_agent.agents.data.metric_diff.ui import render_metric_diff_page
        render_metric_diff_page(app)

    with app.route("SQL Format", "/sqlfmt"):
        from seatunnel_agent.agents.data.sql_fmt.ui import render_sql_fmt_page
        render_sql_fmt_page(app)

    with app.route("MCP Toolbox", "/mcp"):
        render_mcp_page(app)

    # plugin pages: every seatunnel_agent.<pkg>.manifest registers itself
    from .registry import discover, resolve
    for mf in discover():
        with app.route(mf.page_title, mf.route):
            resolve(mf.render)(app)

    return app


def _kill_port(port: int) -> bool:
    """Kill whatever process is listening on *port*. Returns True if killed."""
    import subprocess, sys
    if sys.platform != "win32":
        r = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True,
        )
        for pid in r.stdout.split():
            subprocess.run(["kill", "-9", pid])
        return bool(r.stdout.strip())
    r = subprocess.run(
        ["netstat", "-ano"], capture_output=True, text=True,
    )
    for line in r.stdout.splitlines():
        parts = line.split()
        # netstat -ano: Proto  Local Address  Foreign Address  State  PID
        if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(f":{port}"):
            subprocess.run(["taskkill", "/F", "/PID", parts[4]],
                           capture_output=True)
            return True
    return False


def _port_has_listener(port: int) -> bool:
    """Check if a process is actually LISTENING on *port* (not TIME_WAIT)."""
    import subprocess, sys
    if sys.platform == "win32":
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        return any(f":{port}" in ln and "LISTENING" in ln for ln in r.stdout.splitlines())
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def launch_app(app: gr.Blocks, port: int = 7860, host: str = "127.0.0.1", share: bool = False, api: bool = False) -> None:
    if _port_has_listener(port):
        import os
        if os.getenv("SEATUNNEL_UI_KILL_PORT", "").lower() in ("1", "true", "yes"):
            print(f"[ui] Port {port} in use — killing old process (SEATUNNEL_UI_KILL_PORT is set)...")
            _kill_port(port)
            import time; time.sleep(0.5)
        else:
            raise SystemExit(
                f"[ui] Port {port} is already in use. Stop the process using it, "
                f"choose another port, or set SEATUNNEL_UI_KILL_PORT=1 to kill it automatically."
            )

    # NOTE: launch() builds a FRESH FastAPI instance — anything registered on
    # app.app beforehand is silently discarded (Gradio 6). So launch first
    # without blocking, mount the routers on the instance actually serving,
    # then block.
    app.launch(
        server_name=host,
        server_port=port,
        share=share,
        inbrowser=True,
        css=_CUSTOM_CSS,
        prevent_thread_lock=True,
    )

    if api:
        from fastapi import Depends

        from .common.api_auth import require_api_key
        from seatunnel_agent.agents.data.config_lint.api import router as conflint_api_router
        from seatunnel_agent.agents.data.dag_check.api import router as dagcheck_api_router
        from seatunnel_agent.agents.data.data_lineage.api import router as lineage_api_router
        from seatunnel_agent.agents.data.data_skew.api import router as skew_api_router
        from seatunnel_agent.agents.data.log_inspect.api import router as loginspect_api_router
        from seatunnel_agent.agents.data.metric_diff.api import router as metricdiff_api_router
        from seatunnel_agent.agents.data.pii_scan.api import router as pii_api_router
        from seatunnel_agent.agents.data.schema_drift.api import router as schemadrift_api_router
        from seatunnel_agent.agents.data.sql_fmt.api import router as sqlfmt_api_router
        from seatunnel_agent.agents.data.sql_review.api import router as sql_review_api_router
        from seatunnel_agent.agents.data.sql_testgen.api import router as testgen_api_router
        from seatunnel_agent.agents.data.sql_transpile.api import router as transpile_api_router
        from seatunnel_agent.agents.data.text2sql.api import router as t2s_api_router
        fastapi_app = app.app  # the served instance, now that launch() ran
        # SEATUNNEL_API_KEY (optional) gates every /api route via X-API-Key.
        auth = [Depends(require_api_key)]
        for router in (
            t2s_api_router,
            sql_review_api_router,
            lineage_api_router,
            transpile_api_router,
            skew_api_router,
            pii_api_router,
            loginspect_api_router,
            schemadrift_api_router,
            testgen_api_router,
            conflint_api_router,
            dagcheck_api_router,
            metricdiff_api_router,
            sqlfmt_api_router,
        ):
            fastapi_app.include_router(router, dependencies=auth)
        # plugin routers come from the manifests (see seatunnel_agent.registry)
        from .registry import discover, resolve
        for mf in discover():
            if mf.api:
                fastapi_app.include_router(resolve(mf.api), dependencies=auth)

    app.block_thread()


def main() -> None:
    app = create_ui()
    launch_app(app)


if __name__ == "__main__":
    main()
