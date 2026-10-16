"""Browser smoke for the React Text2SQL page (ticket #64).

Serves the built dist + the real text2sql router in-process and drives a
real connect against a temp SQLite DB. Deselected by default:

    pytest -m uitest tests/test_t2s_page.py
"""

from __future__ import annotations

import socket
import sqlite3
import threading
import time

import pytest

pytestmark = pytest.mark.uitest

DIST = "frontend/text2sql/dist"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(tmp_path):
    from pathlib import Path

    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.text2sql.api import router

    if not (Path(DIST) / "index.html").is_file():
        pytest.skip("text2sql dist not built (cd frontend && npm run build -w @seatunnel/text2sql-frontend)")

    db = tmp_path / "demo.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL)")
    con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    con.commit()
    con.close()

    app = FastAPI()
    app.include_router(router)
    app.mount("/text2sql-next", StaticFiles(directory=DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/text2sql-next/", str(db)
    server.should_exit = True
    t.join(timeout=5)


@pytest.mark.uitest
def test_t2s_page_connects(page_url):
    from playwright.sync_api import expect, sync_playwright

    url, db_path = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        expect(page.get_by_role("heading", name="Text2SQL · Chat BI")).to_be_visible()
        # sqlite path: only the database field is shown
        page.locator("#ds").select_option("sqlite")
        expect(page.get_by_text("Host")).not_to_be_visible()
        page.get_by_label("Database").fill(db_path)
        page.get_by_role("button", name="Connect").click()

        status = page.locator(".st-connect-status")
        expect(status).to_contain_text("Connected", timeout=20000)
        expect(status).to_contain_text("2 tables")
        expect(page.locator(".st-session")).to_contain_text("sqlite")

        browser.close()
