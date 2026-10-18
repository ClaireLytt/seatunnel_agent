"""Browser tests for the React /sqlfmt page (ticket 02).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_conflint_page.py. Deselected by default (needs a browser +
built dist):

    pytest -m uitest tests/test_sqlfmt_page.py

Equivalence coverage for the retired uitest YAML cases (cases/sqlfmt.yaml,
removed in this ticket): FMT1 format round-trip, FMT2 already-formatted,
FMT3 bare SELECT * hint, FMT4 parse failure without traceback, FMT5 demo
directory check, FMT6 English chrome.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.sql_fmt.manifest import MANIFEST
from seatunnel_agent.hub.registry import frontend_dist

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / frontend_dist(MANIFEST)
DEMO_DIR = ROOT / "examples" / "sqlfmt_demo"

MESSY = "select a,b from t where x=1"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url():
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.sql_fmt.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "frontend dist not built (cd frontend && npm run build --workspace sql_fmt)")

    app = FastAPI()
    app.include_router(router)
    app.mount("/sqlfmt", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/sqlfmt/"
    server.should_exit = True
    t.join(timeout=5)


@pytest.mark.uitest
def test_sqlfmt_page_smoke(page_url):
    """FMT6-adjacent: page loads with English chrome; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="SQL Formatter")).to_be_visible()
        expect(page.locator("textarea")).to_be_visible()
        # 7-dialect select defaults to hive
        expect(page.locator("select")).to_have_value("hive")
        expect(page.get_by_role("button", name="Format",
                                exact=True)).to_be_visible()
        expect(page.locator("summary", has_text="Check a directory")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_sqlfmt_format_round_trip(page_url):
    """FMT1: messy SQL formats to an uppercase-keyword report."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").fill(MESSY)
        page.get_by_role("button", name="Format", exact=True).click()

        report = page.locator(".sf-report")
        expect(report).to_be_visible()
        expect(report).to_contain_text("SQL Formatter")
        expect(report).to_contain_text("SELECT")
        browser.close()


@pytest.mark.uitest
def test_sqlfmt_already_formatted(page_url):
    """FMT2: already-formatted SQL reports no change needed."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").fill(MESSY)
        page.get_by_role("button", name="Format", exact=True).click()
        report = page.locator(".sf-report")
        expect(report).to_contain_text("SELECT")
        # feed the formatted body back: grab it via the API for determinism
        import json
        from urllib.request import Request, urlopen
        api = page_url.rsplit("/sqlfmt", 1)[0] + "/api/sqlfmt/format"
        body = json.dumps({"sql": MESSY, "lang": "en"}).encode()
        req = Request(api, data=body,
                      headers={"Content-Type": "application/json"})
        formatted = json.loads(urlopen(req).read())["result"]["formatted"]

        page.locator("textarea").fill(formatted)
        page.get_by_role("button", name="Format", exact=True).click()
        expect(report).to_contain_text("Already formatted")
        browser.close()


@pytest.mark.uitest
def test_sqlfmt_select_star_hint(page_url):
    """FMT3: bare SELECT * yields the style hint in the report."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").fill("select * from t")
        page.get_by_role("button", name="Format", exact=True).click()

        expect(page.locator(".sf-report")).to_contain_text("SELECT *")
        browser.close()


@pytest.mark.uitest
def test_sqlfmt_parse_failure_no_traceback(page_url):
    """FMT4: unparseable SQL reports the failure, never a traceback."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").fill("SELECT FROM WHERE;")
        page.get_by_role("button", name="Format", exact=True).click()

        report = page.locator(".sf-report")
        expect(report).to_be_visible()
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_sqlfmt_directory_check(page_url):
    """FMT5: demo directory check reports the file needing a reformat."""
    from playwright.sync_api import expect, sync_playwright

    assert DEMO_DIR.is_dir(), f"demo dir missing: {DEMO_DIR}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("summary", has_text="Check a directory").click()
        page.get_by_placeholder(
            "Directory containing *.sql (scanned recursively), "
            "e.g. examples/sqlfmt_demo").fill(str(DEMO_DIR))
        page.get_by_role("button", name="Check directory", exact=True).click()

        report = page.locator(".sf-report")
        expect(report).to_be_visible()
        expect(report).to_contain_text("messy.sql")
        browser.close()


@pytest.mark.uitest
def test_sqlfmt_empty_input_warning(page_url):
    """Format with no SQL shows the localized empty warning."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Format", exact=True).click()
        expect(page.get_by_text("Paste some SQL first.")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_sqlfmt_bad_dir_zh(page_url):
    """Directory check with a non-directory shows the localized bad_dir error."""
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

        page.locator("summary", has_text="检查目录").click()
        page.get_by_placeholder(
            "包含 *.sql 的目录（递归扫描），如 examples/sqlfmt_demo").fill(
            str(ROOT / "no_such_dir_xyz"))
        page.get_by_role("button", name="检查目录", exact=True).click()

        expect(page.get_by_text("不是有效目录")).to_be_visible()
        expect(page.get_by_text("no_such_dir_xyz")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_sqlfmt_lang_switch(page_url):
    """st-lang cookie drives the chrome language, and the report follows."""
    from urllib.parse import urlparse

    from playwright.sync_api import expect, sync_playwright

    host = urlparse(page_url).hostname

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # default (no cookie) → English chrome
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        expect(page.get_by_role("button", name="Format",
                                exact=True)).to_be_visible()

        # st-lang=zh-CN cookie (set by the hub) → Chinese chrome + zh report
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "st-lang", "value": "zh-CN",
                          "domain": host, "path": "/"}])
        zh_page = ctx.new_page()
        zh_page.goto(page_url, wait_until="networkidle")
        expect(zh_page.get_by_role("button", name="格式化",
                                   exact=True)).to_be_visible()
        expect(zh_page.locator("textarea")).to_have_attribute(
            "placeholder", "粘贴一条或多条以 ; 分隔的 SQL…")

        zh_page.locator("textarea").fill(MESSY)
        zh_page.get_by_role("button", name="格式化", exact=True).click()
        expect(zh_page.locator(".sf-report")).to_contain_text("SQL 格式化")
        browser.close()
