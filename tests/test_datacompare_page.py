"""Browser smoke for the React /datacompare page (ticket 02 skeleton).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_uitest_page.py. Deselected by default (needs a browser +
built dist):

    pytest -m uitest tests/test_datacompare_page.py
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "datacompare" / "dist"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url():
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.data_comparison.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "frontend dist not built (cd frontend && npm run build --workspace datacompare)")

    app = FastAPI()
    app.include_router(router)
    app.mount("/datacompare", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/datacompare/"
    server.should_exit = True
    t.join(timeout=5)


@pytest.mark.uitest
def test_datacompare_page_smoke(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        # shell rendered; backend meta reached the datasource dropdowns
        expect(page.get_by_role("heading", name="Data Comparison")).to_be_visible()
        for side in ("a", "b"):
            form = page.locator(f"[data-testid=connect-{side}]")
            expect(form).to_be_visible()
            expect(form.locator(f"#ds-{side} option", has_text="SQLite")).to_have_count(1)
            expect(form.get_by_role("button", name="Connect")).to_be_visible()
        # results panel placeholder present
        expect(page.get_by_role("heading", name="Results")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()
