"""Gradio Web UI for SeaTunnel Agent.

Run with:  python -m seatunnel_agent.hub.ui
Or:        seatunnel-agent ui
"""

from __future__ import annotations

import gradio as gr

from seatunnel_agent.hub.css import (
    _CUSTOM_CSS,
)
from seatunnel_agent.hub.pages import (
    _build_ai_hub_html,
    _build_data_hub_html,
    _build_devops_hub_html,
    _build_landing_html,
    _mount_hub,
)


def create_ui() -> gr.Blocks:
    """Multipage app: hub landing page + one dedicated page per agent."""
    # UI-saved LLM settings override .env for this process (see /settings).
    from dotenv import load_dotenv
    load_dotenv()
    from seatunnel_agent.common import settings_store
    settings_store.apply_to_env()

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

    with app.route("Settings", "/settings"):
        from seatunnel_agent.hub.settings_ui import render_settings_page
        render_settings_page(app)

    # plugin pages: every seatunnel_agent.<pkg>.manifest registers itself
    from seatunnel_agent.hub.registry import discover, resolve
    for mf in discover():
        if mf.external:
            continue  # route served outside Gradio (React static mount)
        with app.route(mf.page_title, mf.route):
            resolve(mf.render)(app)

    return app


def _kill_port(port: int) -> bool:
    """Kill whatever process is listening on *port*. Returns True if killed."""
    import subprocess
    import sys
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
    import subprocess
    import sys
    if sys.platform == "win32":
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        return any(f":{port}" in ln and "LISTENING" in ln for ln in r.stdout.splitlines())
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _resolve_ui_auth(host: str, share: bool, insecure: bool) -> tuple[str, str] | None:
    """Credentials for a non-loopback/share launch, or None for no auth.

    Loopback without --share never requires auth. Otherwise the UI is
    reachable from the network, so require SEATUNNEL_UI_AUTH (``user:pass``)
    unless --insecure explicitly waives it.
    """
    if host in _LOOPBACK_HOSTS and not share:
        return None
    import os
    cred = os.getenv("SEATUNNEL_UI_AUTH", "").strip()
    if cred:
        user, sep, pwd = cred.partition(":")
        if not sep or not user or not pwd:
            raise SystemExit(
                "[ui] SEATUNNEL_UI_AUTH must be in 'user:pass' format."
            )
        return (user, pwd)
    if insecure:
        print(
            "[ui] ⚠️  WARNING: UI is exposed on the network WITHOUT authentication "
            "(--insecure). Anyone who can reach this host can use the agents. "
            "Set SEATUNNEL_UI_AUTH=user:pass to enable login."
        )
        return None
    raise SystemExit(
        f"[ui] Refusing to launch without authentication: host={host!r} share={share} "
        "exposes the UI beyond this machine.\n"
        "Set SEATUNNEL_UI_AUTH=user:pass to enable login, "
        "or pass --insecure to launch without auth (not recommended)."
    )


def launch_app(app: gr.Blocks, port: int = 7860, host: str = "127.0.0.1", share: bool = False, api: bool = False, insecure: bool = False) -> None:
    ui_auth = _resolve_ui_auth(host, share, insecure)
    if _port_has_listener(port):
        import os
        if os.getenv("SEATUNNEL_UI_KILL_PORT", "").lower() in ("1", "true", "yes"):
            print(f"[ui] Port {port} in use — killing old process (SEATUNNEL_UI_KILL_PORT is set)...")
            _kill_port(port)
            import time

            time.sleep(0.5)
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
        auth=ui_auth,
        inbrowser=True,
        css=_CUSTOM_CSS,
        prevent_thread_lock=True,
    )

    # UI testing backend + React page: part of the web UI itself, so mounted
    # unconditionally (not gated by --api / API key) on the served instance.
    from seatunnel_agent.agents.devops.ui_testing.api import (
        router as uitest_api_router,
    )
    app.app.include_router(uitest_api_router)

    # SQL Review backend: same deal — the React page calls it directly.
    from seatunnel_agent.agents.data.sql_review.api import (
        router as sql_review_api_router,
    )
    app.app.include_router(sql_review_api_router)

    # SeaTunnel Pipeline Builder backend: same deal — the React page calls it.
    from seatunnel_agent.agents.data.seatunnel.api import (
        router as seatunnel_api_router,
    )
    app.app.include_router(seatunnel_api_router)

    # Data Comparison backend: same deal — the React page calls it.
    from seatunnel_agent.agents.data.data_comparison.api import (
        router as datacompare_api_router,
    )
    app.app.include_router(datacompare_api_router)

    # Config Migrate backend: same deal — the React page calls it.
    from seatunnel_agent.agents.data.config_migrate.api import (
        router as config_migrate_api_router,
    )
    app.app.include_router(config_migrate_api_router)

    # Config Lint backend: same deal — the React page calls it.
    from seatunnel_agent.agents.data.config_lint.api import (
        router as config_lint_api_router,
    )
    app.app.include_router(config_lint_api_router)

    # SQL Formatter backend: same deal — the React page calls it.
    from seatunnel_agent.agents.data.sql_fmt.api import (
        router as sql_fmt_api_router,
    )
    app.app.include_router(sql_fmt_api_router)

    # Rebuilt React pages: every external manifest mounts from the
    # frontend/<name>/dist convention; unbuilt bundles get a hint page.
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.hub.registry import discover, frontend_dist

    def _register_hint(route: str, name: str, legacy: str | None) -> None:
        legacy_html = (
            f" Legacy page: <a href='{legacy}'>{legacy}</a>" if legacy else "")
        body = (
            f"<pre style='margin:40px;font-size:15px'>{name} frontend is "
            f"not built.\n\n  cd frontend &amp;&amp; npm ci &amp;&amp; "
            f"npm run build --workspace {name}\n\nthen restart the UI."
            f"{legacy_html}</pre>")

        @app.app.get(route, include_in_schema=False)
        @app.app.get(route + "/", include_in_schema=False)
        def _unbuilt() -> HTMLResponse:
            return HTMLResponse(body)

    for mf in discover():
        if not mf.external:
            continue
        dist = frontend_dist(mf)
        if (dist / "index.html").is_file():
            app.app.mount(mf.route, StaticFiles(directory=dist, html=True),
                          name=f"{mf.name}-frontend")
        else:
            _register_hint(mf.route, mf.name, mf.legacy)

    if api:
        from fastapi import Depends

        from seatunnel_agent.common.api_auth import require_api_key
        fastapi_app = app.app  # the served instance, now that launch() ran
        # SEATUNNEL_API_KEY (optional) gates every /api route via X-API-Key.
        auth = [Depends(require_api_key)]
        # every REST router comes from the manifests (hub.registry)
        from seatunnel_agent.hub.registry import discover, resolve
        for mf in discover():
            if mf.api:
                fastapi_app.include_router(resolve(mf.api), dependencies=auth)

    app.block_thread()


def main() -> None:
    app = create_ui()
    launch_app(app)


if __name__ == "__main__":
    main()
