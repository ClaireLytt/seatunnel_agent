"""Capture BEFORE screenshots of the legacy Gradio /datacompare page.

Run with PYTHONPATH pointing at a pre-migration worktree (commit e6d0e75)
so the Gradio hub still serves the legacy page. Gradio pages need
wait_until="load" (networkidle never fires on the long-poll connection,
seatunnel precedent) plus a settle sleep. Theme via ?__theme=, language
via the st-lang cookie.
"""
from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

outdir = Path(sys.argv[1])
outdir.mkdir(parents=True, exist_ok=True)

from seatunnel_agent.hub.css import _CUSTOM_CSS  # noqa: E402
from seatunnel_agent.hub.ui import create_ui  # noqa: E402

app = create_ui()
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
app.launch(
    server_name="127.0.0.1",
    server_port=port,
    css=_CUSTOM_CSS,
    prevent_thread_lock=True,
    inbrowser=False,
    quiet=True,
)

shots = (
    ("light", "en", "datacompare-gradio-before-light-full.png"),
    ("dark", "en", "datacompare-gradio-before-dark-full.png"),
    ("light", "zh", "datacompare-gradio-before-zh-full.png"),
)
with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme, lang, fname in shots:
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        ctx.add_cookies([{"name": "st-lang", "value": lang,
                          "url": f"http://127.0.0.1:{port}"}])
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{port}/datacompare?__theme={theme}",
                  wait_until="load")
        time.sleep(6)
        page.screenshot(path=str(outdir / fname), full_page=True)
        ctx.close()
    browser.close()
print("done")
