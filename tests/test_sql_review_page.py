"""Browser smoke for the React /sqlreview page (ticket 01).

Serves the built dist + sql_review API router in-process (uvicorn thread),
mirroring test_uitest_page.py. Deselected by default (needs a browser and a
built dist):

    pytest -m uitest tests/test_sql_review_page.py
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

FRONTEND_DIST = Path("frontend") / "sql_review" / "dist"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(tmp_path, monkeypatch):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.sql_review.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip("frontend dist not built (cd frontend && npm run build --workspace sql_review)")

    # review log goes to a temp dir, not the real history
    from seatunnel_agent.agents.data.sql_review import rlog
    monkeypatch.setattr(rlog.ReviewLogger, "log", lambda self, **kw: None)

    app = FastAPI()
    app.include_router(router)
    app.mount("/sqlreview", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/sqlreview/"
    server.should_exit = True
    t.join(timeout=5)


@pytest.mark.uitest
def test_sql_review_page_smoke(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        # not a white screen; dialect choices baked in
        expect(page.get_by_role("heading", name="SQL Code Review")).to_be_visible()
        expect(page.locator("#dialect option")).to_have_count(10)

        # static review round-trip: SELECT * triggers at least one finding
        page.locator("#sql").fill("SELECT * FROM ods.user_log WHERE a = NULL")
        page.get_by_role("button", name="Start Review").click()
        report = page.locator(".sr-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("CR Report")

        # download button appears once a report exists
        expect(page.get_by_role("button", name="Download Report (.md)")).to_be_visible()

        # static fix round-trip: a = NULL is mechanically fixable, no LLM
        page.get_by_role("button", name="Generate Fixed SQL (LLM)").click()
        expect(page.get_by_text("IS NULL").first).to_be_visible(timeout=15000)

        # DDL / rules collapsibles open and accept input
        page.get_by_role("button", name="Table DDL").click()
        expect(page.locator("#ddl")).to_be_visible()
        page.get_by_role("button", name="Rule config").click()
        expect(page.locator("#rules")).to_be_visible()

        # clear resets form and report
        page.get_by_role("button", name="Clear").click()
        expect(page.locator("#sql")).to_have_value("")
        expect(page.locator(".sr-report")).to_have_count(0)

        browser.close()


@pytest.mark.uitest
def test_sql_review_page_prefill_and_line_jump(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # ?sql=&dialect= prefill (Text2SQL "full review" deep link)
        page.goto(f"{page_url}?sql=select+1+from+t+where+a+%3D+NULL&dialect=mysql",
                  wait_until="networkidle")
        expect(page.locator("#sql")).to_have_value("select 1 from t where a = NULL")
        expect(page.locator("#dialect")).to_have_value("mysql")

        # line links render in the report; clicking selects the SQL line
        page.get_by_role("button", name="Start Review").click()
        link = page.locator('.sr-report a[href*="#srline-"]').first
        expect(link).to_be_visible(timeout=15000)
        link.click()
        sel = page.evaluate(
            "() => { const b = document.querySelector('#sql');"
            " return b.value.substring(b.selectionStart, b.selectionEnd); }")
        assert "a = NULL" in sel

        browser.close()
