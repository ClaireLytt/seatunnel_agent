"""Browser smoke for the React /seatunnel page (walking skeleton).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_uitest_page.py. Deselected by default (needs a browser +
built dist):

    pytest -m uitest tests/test_seatunnel_page.py
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "seatunnel" / "dist"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url():
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.seatunnel.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip("frontend dist not built (cd frontend && npm run build --workspace seatunnel)")

    app = FastAPI()
    app.include_router(router)
    app.mount("/seatunnel", StaticFiles(directory=FRONTEND_DIST, html=True))

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                           log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    deadline = time.time() + 15
    while not server.started:
        if time.time() > deadline:
            pytest.fail("uvicorn did not start")
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}/seatunnel/"
    server.should_exit = True
    t.join(timeout=5)


@pytest.mark.uitest
def test_seatunnel_page_smoke(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        # shell rendered; backend meta reached the header badge
        expect(page.get_by_role("heading",
                                name="SeaTunnel Pipeline Builder")).to_be_visible()
        expect(page.locator(".st-sidebar")).to_be_visible()
        expect(page.locator(".st-chat input")).to_be_visible()
        expect(page.locator("header")).to_contain_text("×4")

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()
