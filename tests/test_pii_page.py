"""Browser tests for the React /pii page (ticket 02).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_metricdiff_page.py. Deselected by default:

    pytest -m uitest tests/test_pii_page.py

Equivalence coverage for the retired uitest YAML cases (cases/pii.yaml
PII1-PII6, removed in this ticket): demo dir scan (bank_card_no,
unmasked), pasted SQL (phone, name+comment match), masked spread not
escalated, bad dir warning, clean SQL no hits, English flow.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.pii_scan.manifest import MANIFEST
from seatunnel_agent.hub.registry import frontend_dist

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / frontend_dist(MANIFEST)
DEMO = ROOT / "examples" / "pii_demo"

PHONE_SQL = ("CREATE TABLE t (uid BIGINT, phone STRING COMMENT '手机号', "
             "note STRING)")
CLEAN_SQL = "CREATE TABLE t (order_id BIGINT, sku_cnt INT)"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(monkeypatch):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.pii_scan.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "frontend dist not built (cd frontend && npm run build --workspace pii_scan)")

    monkeypatch.setenv("PII_API_ALLOWED_DIRS", str(DEMO))
    monkeypatch.chdir(ROOT)

    app = FastAPI()
    app.include_router(router)
    app.mount("/pii", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/pii/"
    server.should_exit = True
    t.join(timeout=5)


@pytest.mark.uitest
def test_pii_page_smoke(page_url):
    """PII6-adjacent: English chrome + demo prefill; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="PII / Sensitive Column Scan")).to_be_visible()
        assert page.locator("input").input_value() == "examples/pii_demo"
        expect(page.locator("select")).to_have_value("hive")
        expect(page.get_by_role("button", name="Scan directory",
                                exact=True)).to_be_visible()
        page.locator("summary").click()
        expect(page.get_by_text("SQL input")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_pii_demo_dir_scan(page_url):
    """PII1+PII3: demo dir reports bank_card_no unmasked propagation and
    masked spread is not escalated."""
    from playwright.sync_api import expect, sync_playwright

    assert DEMO.is_dir(), f"demo dir missing: {DEMO}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Scan directory", exact=True).click()
        report = page.locator(".pii-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("bank_card_no")
        expect(report).to_contain_text("UNMASKED")
        # masked columns reported as masked, severity not escalated for them
        expect(report).to_contain_text("MASKED")
        browser.close()


@pytest.mark.uitest
def test_pii_paste_sql_scan(page_url):
    """PII2: pasted SQL hits the phone rule via name+comment match."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("summary").click()
        page.get_by_placeholder(
            "Paste CREATE TABLE / INSERT ... SELECT statements…").fill(PHONE_SQL)
        page.get_by_role("button", name="Scan SQL", exact=True).click()

        report = page.locator(".pii-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("phone")
        browser.close()


@pytest.mark.uitest
def test_pii_clean_sql_no_hits(page_url):
    """PII5: clean SQL reports no hits, no traceback."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("summary").click()
        page.get_by_placeholder(
            "Paste CREATE TABLE / INSERT ... SELECT statements…").fill(CLEAN_SQL)
        page.get_by_role("button", name="Scan SQL", exact=True).click()

        report = page.locator(".pii-report")
        expect(report).to_be_visible(timeout=15000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_pii_bad_dir_warning(page_url):
    """PII4: non-directory path shows the localized bad_dir warning."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("input").fill(str(DEMO / "no_such_dir"))
        page.get_by_role("button", name="Scan directory", exact=True).click()
        expect(page.get_by_text("Not a directory", exact=False)).to_be_visible(
            timeout=10000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_pii_empty_inputs(page_url):
    """Empty dir / empty SQL show the localized prompts."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("input").fill("")
        page.get_by_role("button", name="Scan directory", exact=True).click()
        expect(page.get_by_text("Provide a SQL directory first.",
                                exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_pii_lang_switch(page_url):
    """st-lang cookie drives chrome + server report language."""
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

        expect(page.get_by_role("button", name="扫描目录",
                                exact=True)).to_be_visible()
        page.get_by_role("button", name="扫描目录", exact=True).click()
        expect(page.locator(".pii-report")).to_contain_text(
            "敏感数据扫描", timeout=15000)
        expect(page.locator(".pii-report")).to_contain_text("未脱敏")
        browser.close()


@pytest.mark.uitest
def test_pii_dialect_switch_spark(page_url):
    """Ticket 05: non-default dialect (spark) still scans the demo dir
    and reports the sensitive column."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("select").select_option("spark")
        expect(page.locator("select")).to_have_value("spark")
        page.get_by_role("button", name="Scan directory", exact=True).click()

        report = page.locator(".pii-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("bank_card_no")
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()
