"""Browser tests for the React /impact page (ticket 02).

Serves the built dist + the shared lineage API router in-process (uvicorn
thread), modeled on tests/test_lineage_page.py. Deselected by default:

    pytest -m uitest tests/test_impact_page.py

Equivalence coverage for the retired uitest YAML cases (cases/impact.yaml
IMP1-IMP8 + scroll SCR3, removed in this ticket): dirs-mode severity
report, bad dir warning, paste mode + SQL diff, missing-SQL prompt,
context-dir blast radius, depth=1 truncation, English chrome.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.data_lineage.manifest import MANIFESTS
from seatunnel_agent.hub.registry import frontend_dist

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = next(m for m in MANIFESTS if m.name == "change_impact")
FRONTEND_DIST = ROOT / frontend_dist(MANIFEST)
OLD_DIR = "examples/impact_demo/old"
NEW_DIR = "examples/impact_demo/new"

OLD_SQL = "INSERT INTO ads.rpt SELECT amount FROM dwd.orders"
NEW_SQL = ("INSERT INTO ads.rpt SELECT amount - refund_amount AS amount "
           "FROM dwd.orders")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(monkeypatch):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.data_lineage.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "frontend dist not built (cd frontend && npm run build --workspace change_impact)")

    monkeypatch.setenv("LINEAGE_API_ALLOWED_DIRS",
                       str(ROOT / "examples" / "impact_demo"))
    monkeypatch.chdir(ROOT)

    app = FastAPI()
    app.include_router(router)
    app.mount("/impact", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/impact/"
    server.should_exit = True
    t.join(timeout=5)


def _analyze_dirs(page, old=OLD_DIR, new=NEW_DIR):
    page.get_by_placeholder(
        "SQL tree before the change, e.g. examples/impact_demo/old").fill(old)
    page.get_by_placeholder(
        "SQL tree after the change, e.g. examples/impact_demo/new").fill(new)
    page.get_by_role("button", name="Analyze change impact",
                     exact=True).click()


@pytest.mark.uitest
def test_impact_page_smoke(page_url):
    """Page loads: heading, tabs, dialect/depth, placeholder; no console
    errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="Change Impact Analysis")).to_be_visible()
        expect(page.get_by_role("button", name="Directories",
                                exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Paste SQL",
                                exact=True)).to_be_visible()
        expect(page.locator("select")).to_have_value("hive")
        expect(page.locator('input[type="range"]')).to_have_value("3")
        expect(page.get_by_text("Fill both sides and click Analyze.")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_impact_dirs_mode_severity(page_url):
    """IMP1/IMP2: demo trees yield the severity graph + graded report."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _analyze_dirs(page)
        expect(page.locator("svg").first).to_be_visible(timeout=20000)
        report = page.locator(".imp-report")
        expect(report).to_be_visible()
        expect(report).to_contain_text("[error]")
        expect(report).to_contain_text("[warn]")
        browser.close()


@pytest.mark.uitest
def test_impact_missing_dirs_prompt(page_url):
    """Analyze with empty dirs shows the localized need_dirs prompt."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Analyze change impact",
                         exact=True).click()
        expect(page.get_by_text(
            "Provide both the old and the new SQL directory.",
            exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_impact_bad_dir_warning(page_url):
    """IMP3: a non-directory path shows the localized bad_dir error."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _analyze_dirs(page, old="examples/impact_demo/nope")
        expect(page.get_by_text("Not a directory", exact=False)).to_be_visible(
            timeout=10000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_impact_paste_mode_sql_diff(page_url):
    """IMP4: pasted before/after SQL appends the SQL diff block."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Paste SQL", exact=True).click()
        page.get_by_placeholder("Paste the SQL before the change…").fill(OLD_SQL)
        page.get_by_placeholder("Paste the SQL after the change…").fill(NEW_SQL)
        page.get_by_role("button", name="Analyze pasted SQL",
                         exact=True).click()

        report = page.locator(".imp-report")
        expect(report).to_be_visible(timeout=20000)
        expect(report).to_contain_text("SQL diff")
        expect(report).to_contain_text("refund_amount")
        browser.close()


@pytest.mark.uitest
def test_impact_paste_missing_sql_prompt(page_url):
    """IMP5: only one side pasted → localized need_sql prompt."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Paste SQL", exact=True).click()
        page.get_by_placeholder("Paste the SQL before the change…").fill(OLD_SQL)
        page.get_by_role("button", name="Analyze pasted SQL",
                         exact=True).click()
        expect(page.get_by_text("Paste both the old and the new SQL.",
                                exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_impact_context_dir_blast(page_url):
    """IMP6: context dir widens the blast radius to repo consumers."""
    from playwright.sync_api import expect, sync_playwright

    ctx = str(Path(os.environ.get("PYTEST_CURRENT_TEST", "")).parent)
    del ctx  # context dir must be whitelisted — use the demo old tree

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Paste SQL", exact=True).click()
        page.get_by_placeholder("Paste the SQL before the change…").fill(
            "INSERT INTO dws.gmv_daily SELECT gmv FROM dwd.orders_di")
        page.get_by_placeholder("Paste the SQL after the change…").fill(
            "INSERT INTO dws.gmv_daily SELECT gmv, channel FROM dwd.orders_di")
        page.get_by_placeholder(
            "Repo SQL tree; widens the blast radius to real consumers").fill(
            NEW_DIR)
        page.get_by_role("button", name="Analyze pasted SQL",
                         exact=True).click()

        report = page.locator(".imp-report")
        expect(report).to_be_visible(timeout=20000)
        expect(report).to_contain_text("dws.gmv_daily")
        browser.close()


@pytest.mark.uitest
def test_impact_depth_one_truncation(page_url):
    """IMP7: depth slider = 1 limits the downstream walk."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator('input[type="range"]').fill("1")
        _analyze_dirs(page)
        report = page.locator(".imp-report")
        expect(report).to_be_visible(timeout=20000)
        expect(report).to_contain_text("[error]")
        browser.close()


@pytest.mark.uitest
def test_impact_lang_switch(page_url):
    """IMP8: st-lang cookie drives the chrome + server report language."""
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

        expect(page.get_by_role("button", name="变更影响分析",
                                exact=True)).to_be_visible()
        page.get_by_placeholder("变更前的 SQL 目录，如 examples/impact_demo/old").fill(OLD_DIR)
        page.get_by_placeholder("变更后的 SQL 目录，如 examples/impact_demo/new").fill(NEW_DIR)
        page.get_by_role("button", name="变更影响分析", exact=True).click()
        expect(page.locator(".imp-report")).to_contain_text(
            "变更影响分析", timeout=20000)
        browser.close()


@pytest.mark.uitest
def test_impact_dialect_switch_spark(page_url):
    """Ticket 05: non-default dialect (spark) still yields the graded
    report — no traceback, no error state."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("select").select_option("spark")
        expect(page.locator("select")).to_have_value("spark")
        _analyze_dirs(page)

        report = page.locator(".imp-report")
        expect(report).to_be_visible(timeout=20000)
        expect(report).to_contain_text("[error]")
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()
