"""Browser tests for the React /transpile page (ticket 02).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_sqlfmt_page.py. Deselected by default (needs a browser +
built dist):

    pytest -m uitest tests/test_transpile_page.py

Equivalence coverage for the retired uitest YAML cases (cases/transpile.yaml,
removed in this ticket): TRP1 hive→doris translate, TRP2 unknown UDF needs
manual work, TRP3 bad SQL warning without traceback, TRP4 retarget
starrocks, TRP5 batch demo dir, TRP6 LLM advice (deterministic structured
path), TRP7 batch with output dir, TRP8 bad dir warning, TRP9 English
chrome. Plus the sql_review localStorage bridge pickup.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.sql_transpile.manifest import MANIFEST
from seatunnel_agent.hub.registry import frontend_dist

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / frontend_dist(MANIFEST)
DEMO_DIR = ROOT / "examples" / "transpile_demo"

HIVE_JSON_SQL = "SELECT get_json_object(j, '$.a') FROM t"
UDF_SQL = "SELECT my_udf(x) FROM t"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(monkeypatch, tmp_path):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.sql_transpile.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "frontend dist not built (cd frontend && npm run build --workspace sql_transpile)")

    import os
    monkeypatch.setenv("TRANSPILE_API_ALLOWED_DIRS",
                       os.pathsep.join([str(ROOT), str(tmp_path)]))

    app = FastAPI()
    app.include_router(router)
    app.mount("/transpile", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/transpile/", tmp_path
    server.should_exit = True
    t.join(timeout=5)


@pytest.mark.uitest
def test_transpile_page_smoke(page_url):
    """TRP9-adjacent: page loads with English chrome; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="SQL Dialect Translation")).to_be_visible()
        # dialect pair: source defaults to auto, target to doris
        expect(page.locator("select").first).to_have_value("auto")
        expect(page.locator("select").nth(1)).to_have_value("doris")
        expect(page.get_by_role("button", name="Translate",
                                exact=True)).to_be_visible()
        expect(page.locator("summary",
                            has_text="Batch translate a directory")).to_be_visible()
        expect(page.locator("summary", has_text="LLM advice")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_transpile_hive_to_doris(page_url):
    """TRP1: get_json_object → JSON_EXTRACT, fully automatic."""
    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        page.locator("textarea").fill(HIVE_JSON_SQL)
        page.get_by_role("button", name="Translate", exact=True).click()

        expect(page.locator("pre").first).to_contain_text("JSON_EXTRACT")
        expect(page.locator(".tr-report")).to_contain_text("auto 1")
        browser.close()


@pytest.mark.uitest
def test_transpile_unknown_udf_needs_manual(page_url):
    """TRP2: unknown UDF lands in the needs-manual bucket."""
    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        page.locator("textarea").fill(UDF_SQL)
        page.get_by_role("button", name="Translate", exact=True).click()

        expect(page.locator(".tr-report")).to_contain_text("manual 1")
        browser.close()


@pytest.mark.uitest
def test_transpile_bad_sql_no_traceback(page_url):
    """TRP3: unparseable SQL yields a readable warning, never a traceback."""
    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        page.locator("textarea").fill("SELECT FROM WHERE;")
        page.get_by_role("button", name="Translate", exact=True).click()

        expect(page.locator(".tr-report")).to_be_visible()
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_transpile_retarget_starrocks(page_url):
    """TRP4: switching the target dialect retargets the report header."""
    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        page.locator("select").nth(1).select_option("starrocks")
        page.locator("textarea").fill(HIVE_JSON_SQL)
        page.get_by_role("button", name="Translate", exact=True).click()

        expect(page.locator(".tr-report")).to_contain_text("hive → starrocks")
        browser.close()


@pytest.mark.uitest
def test_transpile_batch_demo_dir(page_url):
    """TRP5: batch over the demo dir reports per-file stats."""
    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    assert DEMO_DIR.is_dir(), f"demo dir missing: {DEMO_DIR}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        page.locator("summary", has_text="Batch translate a directory").click()
        page.get_by_placeholder(
            "Directory containing *.sql files (scanned recursively)").fill(
            str(DEMO_DIR))
        page.get_by_role("button", name="Batch translate", exact=True).click()

        report = page.locator(".tr-report")
        expect(report).to_be_visible()
        expect(report).to_contain_text("06_broken.sql")
        browser.close()


@pytest.mark.uitest
def test_transpile_batch_with_out_dir(page_url):
    """TRP7: batch with a whitelisted output dir writes translated files."""
    from playwright.sync_api import expect, sync_playwright

    url, tmp_path = page_url
    out = tmp_path / "trp_out"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        page.locator("summary", has_text="Batch translate a directory").click()
        page.get_by_placeholder(
            "Directory containing *.sql files (scanned recursively)").fill(
            str(DEMO_DIR))
        page.get_by_placeholder(
            "Translated files mirror the input tree when set").fill(str(out))
        page.get_by_role("button", name="Batch translate", exact=True).click()

        expect(page.locator(".tr-report")).to_be_visible()
        browser.close()

    assert list(out.rglob("*.sql")), "no translated files written"


@pytest.mark.uitest
def test_transpile_bad_dir_zh(page_url):
    """TRP8: non-directory path shows the localized bad_dir error (zh)."""
    from urllib.parse import urlparse

    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    host = urlparse(url).hostname

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "st-lang", "value": "zh-CN",
                          "domain": host, "path": "/"}])
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle")

        page.locator("summary", has_text="批量翻译目录").click()
        page.get_by_placeholder("包含 *.sql 的目录（递归扫描）").fill(
            str(ROOT / "no_such_dir_xyz"))
        page.get_by_role("button", name="批量翻译", exact=True).click()

        expect(page.get_by_text("不是有效目录")).to_be_visible()
        expect(page.get_by_text("no_such_dir_xyz")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_transpile_advice_deterministic_path(page_url):
    """TRP6 (deterministic): advice button after a clean translate reports
    the structured 'none' state — no LLM call needed."""
    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        page.locator("textarea").fill(HIVE_JSON_SQL)
        page.get_by_role("button", name="Translate", exact=True).click()
        expect(page.locator(".tr-report")).to_contain_text("auto 1")

        page.locator("summary", has_text="LLM advice").click()
        page.get_by_role("button", name="Generate LLM advice",
                         exact=True).click()
        expect(page.get_by_text("No findings that need LLM advice."))\
            .to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_transpile_bridge_pickup(page_url):
    """SQL handed over from sql_review via localStorage prefills the box."""
    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # seed the bridge key on the same origin before the app mounts
        page.goto(url, wait_until="commit")
        page.evaluate(
            "localStorage.setItem('st_transpile_sql', 'SELECT 42')")
        page.goto(url, wait_until="networkidle")

        expect(page.locator("textarea")).to_have_value("SELECT 42")
        # drained after pickup
        assert page.evaluate(
            "localStorage.getItem('st_transpile_sql')") is None
        browser.close()


@pytest.mark.uitest
def test_transpile_lang_switch(page_url):
    """st-lang cookie drives the chrome language, and the report follows."""
    from urllib.parse import urlparse

    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    host = urlparse(url).hostname

    with sync_playwright() as p:
        browser = p.chromium.launch()

        ctx = browser.new_context()
        ctx.add_cookies([{"name": "st-lang", "value": "zh-CN",
                          "domain": host, "path": "/"}])
        zh_page = ctx.new_page()
        zh_page.goto(url, wait_until="networkidle")
        expect(zh_page.get_by_role("button", name="翻译",
                                   exact=True)).to_be_visible()
        expect(zh_page.locator("textarea")).to_have_attribute(
            "placeholder", "粘贴一条或多条以 ; 分隔的 SQL…")

        zh_page.locator("textarea").fill(HIVE_JSON_SQL)
        zh_page.get_by_role("button", name="翻译", exact=True).click()
        expect(zh_page.locator(".tr-report")).to_contain_text("全自动 1")
        browser.close()


@pytest.mark.uitest
def test_transpile_copy_sql_clipboard(page_url):
    """Ticket 01: Copy writes the translated SQL to the clipboard
    (clipboard-read/clipboard-write context permissions + readText)."""
    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            permissions=["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle")

        page.locator("textarea").fill(HIVE_JSON_SQL)
        page.get_by_role("button", name="Translate", exact=True).click()
        copy_btn = page.get_by_role("button", name="Copy", exact=True)
        expect(copy_btn).to_be_visible()

        shown_sql = copy_btn.locator("xpath=../../pre").text_content() or ""
        copy_btn.click()
        expect(page.get_by_text("Copied", exact=False)).to_be_visible()

        clipboard = page.evaluate("() => navigator.clipboard.readText()")
        # Windows Chromium normalizes clipboard text to CRLF
        clipboard = clipboard.replace("\r\n", "\n")
        assert clipboard.strip() == shown_sql.strip()
        assert "JSON_EXTRACT" in clipboard
        browser.close()


@pytest.mark.uitest
def test_transpile_explicit_source_dialect(page_url):
    """Ticket 05: an explicitly selected source dialect (hive, not auto)
    translates successfully and the report names the pair."""
    from playwright.sync_api import expect, sync_playwright

    url, _ = page_url
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        page.locator("select").first.select_option("hive")
        expect(page.locator("select").first).to_have_value("hive")
        page.locator("textarea").fill(HIVE_JSON_SQL)
        page.get_by_role("button", name="Translate", exact=True).click()

        expect(page.locator("pre").first).to_contain_text("JSON_EXTRACT")
        expect(page.locator(".tr-report")).to_contain_text("hive → doris")
        browser.close()
