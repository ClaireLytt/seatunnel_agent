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
    app.mount("/text2sql", StaticFiles(directory=DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/text2sql/", str(db)
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
        # connected session opens the chat panel (#65)
        expect(page.get_by_role("button", name="Send")).to_be_visible()

        browser.close()


@pytest.fixture()
def chat_page_url(tmp_path, monkeypatch):
    """Same in-process server, but the agent is faked so the chat stream
    (not the LLM) is the seam under test."""
    from pathlib import Path

    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.text2sql import api as t2s_api

    if not (Path(DIST) / "index.html").is_file():
        pytest.skip("text2sql dist not built")

    class FakeAgent:
        def __init__(self):
            self._on_event = None
            self.runtime = type("R", (), {"ds_type": "sqlite"})()
            self.runtime.store = type(
                "S", (), {"tables": [type("T", (), {"full_name": "orders"})()]})()

        def set_event_hook(self, cb):
            self._on_event = cb

        def chat(self, message):
            self._on_event("text", {"text": "looking at orders"})
            rows = [[f"r{i}", i] for i in range(60)]
            self._on_event("tool_result", {
                "name": "execute_sql",
                "result": {"sql": "SELECT region, amount FROM orders",
                           "columns": ["region", "amount"], "rows": rows,
                           "row_count": 60}})
            self._on_event("final_answer", {"text": "orders has 42 rows"})
            return "orders has 42 rows"

    monkeypatch.setattr(t2s_api, "_build_agent", lambda *a, **k: FakeAgent())

    app = FastAPI()
    app.include_router(t2s_api.router)
    app.mount("/text2sql", StaticFiles(directory=DIST, html=True))
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
    yield f"http://127.0.0.1:{port}/text2sql/"
    server.should_exit = True
    t.join(timeout=5)


@pytest.mark.uitest
def test_t2s_chat_streams_and_renders_table(chat_page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url, wait_until="networkidle")

        page.locator("#ds").select_option("sqlite")
        page.get_by_label("Database").fill("whatever.db")
        page.get_by_role("button", name="Connect").click()
        expect(page.locator(".st-connect-status")).to_contain_text(
            "Connected", timeout=15000)

        page.get_by_placeholder("Ask about your data").fill("how many orders?")
        page.get_by_role("button", name="Send").click()

        expect(page.locator(".st-msg-user")).to_contain_text("how many orders?")
        expect(page.locator(".st-msg-bot").first).to_contain_text(
            "looking at orders", timeout=15000)
        table = page.locator(".st-result table")
        expect(table).to_be_visible()
        expect(table).to_contain_text("region")
        expect(table).to_contain_text("r0")
        expect(page.get_by_text("orders has 42 rows")).to_be_visible()

        # ticket #66: pagination for >20 rows, server-detected Recharts chart,
        # client CSV export control
        expect(page.locator(".st-pager")).to_contain_text("1/2")
        # 60 rows exceed auto-detect caps (server returns None) — the manual
        # type override is the behavior under test here
        expect(page.locator(".st-chart")).to_have_count(0)
        page.get_by_label("Chart type").select_option("bar")
        expect(page.locator(".st-chart svg")).to_be_visible()
        expect(page.locator(".st-csv")).to_be_visible()
        page.locator(".st-pager button").nth(1).click()
        expect(table).to_contain_text("r59")

        # new chat clears the transcript
        page.get_by_role("button", name="New chat").click()
        expect(page.locator(".st-msg-user")).to_have_count(0)

        browser.close()


@pytest.mark.uitest
def test_t2s_schema_filter_and_browser(page_url):
    """Ticket #68: sidebar table filter narrows the session; the #schema
    view lists tables and shows column detail. Real SQLite session."""
    from playwright.sync_api import expect, sync_playwright

    url, db_path = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.locator("#ds").select_option("sqlite")
        page.get_by_label("Database").fill(db_path)
        page.get_by_role("button", name="Connect").click()
        expect(page.locator(".st-connect-status")).to_contain_text(
            "Connected", timeout=20000)

        # narrow to one table via the filter panel
        panel = page.locator(".st-schema-panel")
        expect(panel).to_contain_text("2/2")
        panel.get_by_role("button").first.click()  # expand
        panel.get_by_role("button", name="None").click()
        panel.get_by_label("orders").check()
        panel.locator(".st-filter-apply").click()
        expect(panel).to_contain_text("1/2", timeout=15000)

        # schema browser view shows the remaining table's columns
        page.get_by_role("link", name="Schema browser").click()
        browser_view = page.locator(".st-schema-browser")
        expect(browser_view).to_contain_text("orders")
        browser_view.get_by_role("button", name="orders").click()
        expect(page.locator(".st-table-detail")).to_contain_text("amount")

        browser.close()


@pytest.mark.uitest
def test_t2s_history_view_qlog(chat_page_url, tmp_path, monkeypatch):
    """Ticket #69: the #history view lists seeded qlog records and clears."""
    from playwright.sync_api import expect, sync_playwright

    from seatunnel_agent.agents.data.text2sql import api as t2s_api
    from seatunnel_agent.agents.data.text2sql.qlog import QueryLogger

    logger = QueryLogger(log_dir=tmp_path)
    logger.log("how many orders", "SELECT count(*) FROM orders", "ok",
               exec_time_ms=7)
    monkeypatch.setattr(t2s_api, "_query_logger", lambda: logger)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(chat_page_url + "#history", wait_until="networkidle")

        view = page.locator(".st-history-view")
        expect(view).to_contain_text("how many orders", timeout=15000)
        view.get_by_text("how many orders").click()
        expect(page.locator(".st-qlog-detail")).to_contain_text("count(*)")
        view.get_by_role("button", name="Clear all").click()
        expect(view).not_to_contain_text("how many orders")

        browser.close()
