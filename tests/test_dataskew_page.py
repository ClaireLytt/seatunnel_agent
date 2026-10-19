"""Browser tests for the React /dataskew page (ticket 04).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_transpile_page.py. Deselected by default (needs a browser +
built dist):

    pytest -m uitest tests/test_dataskew_page.py

Equivalence coverage for the retired uitest YAML cases (cases/dataskew.yaml
DSK1-DSK21, scroll SCR9, fixture connect_skew_sqlite — removed in this
ticket): static rule findings (DSK2/DSK5), clean SQL (DSK7), clear (DSK8),
English report (DSK10), verify without connection (DSK11/DSK19), SQLite
connect + live probe (DSK12/DSK13), consistency without optimized SQL
(DSK14), history refresh+load (DSK16), file upload (DSK18), plus the
sql_review localStorage bridge pickup. DSKA1 (real LLM) stays manual; the
LLM path is covered deterministically by the llm_unavailable fallback at
the API layer (tests/test_dataskew_session_api.py).
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.data_skew.manifest import MANIFEST
from seatunnel_agent.hub.registry import frontend_dist

ROOT = Path(__file__).resolve().parents[1]
_DEMO_DB = ""  # set by the page_url fixture (seeded per-test)
FRONTEND_DIST = ROOT / frontend_dist(MANIFEST)

DISTINCT_SQL = "SELECT COUNT(DISTINCT user_id) FROM ods.user_log"
GROUP_SQL = "SELECT status, COUNT(*) FROM dc_test_orders_a GROUP BY status"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(monkeypatch, tmp_path):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.data_skew.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "frontend dist not built (cd frontend && npm run build --workspace data_skew)")

    monkeypatch.setenv("SEATUNNEL_SKEW_HISTORY_PATH",
                       str(tmp_path / "history.jsonl"))
    # seeded SQLite demo db (the repo copy is gitignored; CI builds it)
    from seatunnel_agent.agents.devops.ui_testing.seed_sqlite import seed_sqlite

    global _DEMO_DB
    _DEMO_DB = str(seed_sqlite(tmp_path / "uitest_demo.db"))

    app = FastAPI()
    app.include_router(router)
    app.mount("/dataskew", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/dataskew/"
    server.should_exit = True
    t.join(timeout=5)


def _connect_sqlite(page):
    """Fixture-equivalent of the retired connect_skew_sqlite YAML steps."""
    from playwright.sync_api import expect

    page.locator("summary", has_text="Connect data source").click()
    # selects: 0=dialect 1=mode 2=preset 3=ds_type 4=sample
    page.locator("select").nth(3).select_option("sqlite")
    page.get_by_text("Database").locator("xpath=following-sibling::input").fill(
        _DEMO_DB)
    page.get_by_role("button", name="Connect", exact=True).click()
    expect(page.get_by_text("Connected", exact=False)).to_be_visible(
        timeout=10000)


@pytest.mark.uitest
def test_dataskew_page_smoke(page_url):
    """Page loads: heading, selects, all four accordions; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="SQL Data Skew Analyzer")).to_be_visible()
        expect(page.locator("#dsk-sql-box")).to_be_visible()
        expect(page.get_by_role("button", name="Analyze Skew",
                                exact=True)).to_be_disabled()  # empty SQL
        for acc in ("Connect data source", "SeaTunnel split-key check",
                    "Runtime diagnosis", "Analysis history"):
            expect(page.locator("summary", has_text=acc)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_dataskew_static_distinct_finding_zh(page_url):
    """DSK2: COUNT(DISTINCT) single-point aggregation flagged (zh report)."""
    from urllib.parse import urlparse

    from playwright.sync_api import expect, sync_playwright

    host = urlparse(page_url).hostname
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "st-lang", "value": "zh-CN",
                          "domain": host, "path": "/"}])
        page = ctx.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(DISTINCT_SQL)
        page.get_by_role("button", name="开始分析", exact=True).click()

        report = page.locator(".dsk-report-card")
        expect(report).to_be_visible(timeout=10000)
        expect(report).to_contain_text("COUNT(DISTINCT)")
        expect(report).to_contain_text("下载报告")
        browser.close()


@pytest.mark.uitest
def test_dataskew_clean_sql_no_optimized(page_url):
    """DSK7/DSK10: clean SQL yields an English report, no optimized-SQL
    download, no traceback."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill("SELECT id FROM t WHERE id = 1")
        page.get_by_role("button", name="Analyze Skew", exact=True).click()

        report = page.locator(".dsk-report-card")
        expect(report).to_be_visible(timeout=10000)
        expect(page.get_by_role("button", name="Download Report (.md)",
                                exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Download Optimized SQL (.sql)",
                                exact=True)).to_have_count(0)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_dataskew_clear_resets(page_url):
    """DSK8: Clear empties the editor and restores the placeholder."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(DISTINCT_SQL)
        page.get_by_role("button", name="Analyze Skew", exact=True).click()
        expect(page.locator(".dsk-report-card")).to_be_visible(timeout=10000)

        page.get_by_role("button", name="Clear", exact=True).click()
        expect(page.locator("#dsk-sql-box")).to_have_value("")
        expect(page.get_by_text(
            "The skew analysis report will appear here")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_dataskew_verify_needs_connection(page_url):
    """DSK11/DSK19: Verify without a connection shows the localized hint."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(GROUP_SQL)
        page.locator("summary", has_text="Connect data source").click()
        page.get_by_role("button", name="Verify Skew (live data)",
                         exact=True).click()
        expect(page.get_by_text("Connect a data source first",
                                exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_dataskew_sqlite_connect_and_probe(page_url):
    """DSK12/DSK13: SQLite connect, then a live probe appends the measured
    section to the report."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(GROUP_SQL)
        page.get_by_role("button", name="Analyze Skew", exact=True).click()
        expect(page.locator(".dsk-report-card")).to_be_visible(timeout=10000)

        _connect_sqlite(page)
        page.get_by_role("button", name="Verify Skew (live data)",
                         exact=True).click()
        expect(page.locator(".dsk-report-card")).to_contain_text(
            "Skew Verification", timeout=15000)
        browser.close()


@pytest.mark.uitest
def test_dataskew_consistency_needs_optimized(page_url):
    """DSK14: consistency without an optimized SQL shows the hint."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(GROUP_SQL)
        _connect_sqlite(page)
        page.get_by_role("button",
                         name="Measure Consistency (runs both SQLs)",
                         exact=True).click()
        expect(page.get_by_text("Generate the optimized SQL first",
                                exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_dataskew_splitkey_needs_conf(page_url):
    """Split-key check with an empty config shows the localized hint."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _connect_sqlite(page)
        page.locator("summary", has_text="SeaTunnel split-key check").click()
        page.get_by_role("button", name="Check split key", exact=True).click()
        expect(page.get_by_text("Paste a SeaTunnel job config first",
                                exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_dataskew_history_refresh_and_load(page_url):
    """DSK16: history refresh lists the run; load refills the editor."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(DISTINCT_SQL)
        page.get_by_role("button", name="Analyze Skew", exact=True).click()
        expect(page.locator(".dsk-report-card")).to_be_visible(timeout=10000)

        page.locator("summary", has_text="Analysis history").click()
        page.get_by_role("button", name="Refresh", exact=True).click()
        hist_table = page.locator("aside table")  # report tables live in main
        expect(hist_table).to_be_visible()
        expect(hist_table).to_contain_text("COUNT(DISTINCT")

        page.get_by_role("button", name="Clear", exact=True).click()
        expect(page.locator("#dsk-sql-box")).to_have_value("")
        page.get_by_role("button", name="Load selected", exact=True).click()
        expect(page.locator("#dsk-sql-box")).to_have_value(DISTINCT_SQL)
        browser.close()


@pytest.mark.uitest
def test_dataskew_upload_fills_editor(page_url, tmp_path):
    """DSK18: uploading a .sql file fills the editor."""
    from playwright.sync_api import expect, sync_playwright

    sql_file = tmp_path / "upload_demo.sql"
    sql_file.write_text(DISTINCT_SQL, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator('input[type="file"]').first.set_input_files(str(sql_file))
        expect(page.locator("#dsk-sql-box")).to_have_value(DISTINCT_SQL)
        browser.close()


@pytest.mark.uitest
def test_dataskew_bridge_pickup(page_url):
    """SQL handed over from sql_review via localStorage prefills the box."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="commit")
        page.evaluate("localStorage.setItem('st_dataskew_sql', 'SELECT 42')")
        page.goto(page_url, wait_until="networkidle")

        expect(page.locator("#dsk-sql-box")).to_have_value("SELECT 42")
        assert page.evaluate(
            "localStorage.getItem('st_dataskew_sql')") is None
        browser.close()


@pytest.mark.uitest
def test_dataskew_conn_cookie_handoff(page_url):
    """st_dataskew_conn cookie pre-fills the connection form (no password)
    and opens the accordion."""
    import json
    from urllib.parse import quote, urlparse

    from playwright.sync_api import expect, sync_playwright

    host = urlparse(page_url).hostname
    cookie = quote(json.dumps({
        "ds_type": "mysql", "host": "db-b", "port": 3306,
        "database": "shop", "username": "ro"}))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "st_dataskew_conn", "value": cookie,
                          "domain": host, "path": "/"}])
        page = ctx.new_page()
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_text("Connection handed over",
                                exact=False)).to_be_visible()
        expect(page.get_by_text("Host").locator(
            "xpath=following-sibling::input")).to_have_value("db-b")
        browser.close()


def _download_text(download) -> str:
    """Reusable download-assertion helper: save and read the file's text."""
    return Path(download.path()).read_text(encoding="utf-8")


STUB_OPTIMIZED_SQL = ("SELECT user_id, SUM(cnt) FROM ("
                      "SELECT user_id, COUNT(*) AS cnt FROM ods.user_log "
                      "GROUP BY user_id, bucket) t GROUP BY user_id")


@pytest.fixture()
def stub_llm(monkeypatch):
    """Deterministic (zero-token) LLM mode: stub the agent + settings at
    their source modules so /api/skew/analyze mode=llm returns an optimized
    SQL without calling a model. Reusable pattern for LLM-gated controls."""
    from seatunnel_agent.agents.data.data_skew import agent as agent_mod
    from seatunnel_agent.agents.data.data_skew.agent import SkewAnalysisResult
    from seatunnel_agent.agents.data.data_skew.report import SkewReport
    from seatunnel_agent.common import config as config_mod

    class _StubAgent:
        def __init__(self, *args, **kwargs):
            pass

        def analyze(self, sql, use_llm=True, probe_context=""):
            rep = SkewReport(optimized_sql=STUB_OPTIMIZED_SQL)
            return SkewAnalysisResult(
                report=rep, used_llm=True,
                markdown="## Stub Report\n\nGROUP BY hotspot rewritten.")

    monkeypatch.setattr(agent_mod, "DataSkewAgent", _StubAgent)
    monkeypatch.setattr(config_mod, "load_settings", lambda *a, **kw: object())


def _analyze_llm(page):
    """Run an analysis in (stubbed) LLM mode so the optimized-SQL card with
    its download + Copy buttons renders."""
    from playwright.sync_api import expect

    page.locator("#dsk-sql-box").fill(GROUP_SQL)
    # selects: 0=dialect 1=mode 2=preset 3=ds_type 4=sample
    page.locator("select").nth(1).select_option("llm")
    page.get_by_role("button", name="Analyze Skew", exact=True).click()
    expect(page.locator(".dsk-report-card")).to_be_visible(timeout=10000)


@pytest.mark.uitest
def test_dataskew_download_report(page_url):
    """Ticket 01: Download Report really downloads — suggested_filename is
    data_skew_report.md and the content is the non-empty report."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("#dsk-sql-box").fill(DISTINCT_SQL)
        page.get_by_role("button", name="Analyze Skew", exact=True).click()
        expect(page.locator(".dsk-report-card")).to_be_visible(timeout=10000)

        with page.expect_download() as dl:
            page.get_by_role("button", name="Download Report (.md)",
                             exact=True).click()
        report = dl.value
        assert report.suggested_filename == "data_skew_report.md"
        report_text = _download_text(report)
        assert report_text.strip()
        assert "COUNT(DISTINCT" in report_text
        browser.close()


@pytest.mark.uitest
def test_dataskew_download_optimized_sql(page_url, stub_llm):
    """Ticket 01: Download Optimized SQL really downloads —
    my_task_optimized.sql with the optimized SQL as content."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _analyze_llm(page)
        with page.expect_download() as dl:
            page.get_by_role("button", name="Download Optimized SQL (.sql)",
                             exact=True).click()
        sql_dl = dl.value
        assert sql_dl.suggested_filename == "my_task_optimized.sql"
        assert _download_text(sql_dl).strip() == STUB_OPTIMIZED_SQL
        browser.close()


@pytest.mark.uitest
def test_dataskew_copy_sql_clipboard(page_url, stub_llm):
    """Ticket 01: Copy writes the optimized SQL to the clipboard
    (clipboard-read/clipboard-write context permissions + readText)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            permissions=["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        page.goto(page_url, wait_until="networkidle")

        _analyze_llm(page)
        page.get_by_role("button", name="Copy", exact=True).click()
        expect(page.get_by_text("Copied", exact=False)).to_be_visible()

        clipboard = page.evaluate("() => navigator.clipboard.readText()")
        assert clipboard == STUB_OPTIMIZED_SQL
        browser.close()
