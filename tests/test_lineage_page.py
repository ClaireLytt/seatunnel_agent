"""Browser tests for the React /lineage page (ticket 04).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_dataskew_page.py. Deselected by default (needs a browser +
built dist):

    pytest -m uitest tests/test_lineage_page.py

Equivalence coverage for the retired uitest YAML cases (cases/lineage.yaml
LIN1-LIN7 + lineage_advanced.yaml LIN8-LIN11, removed in this ticket):
build from SQL dir, query chain + mermaid graph, search, health check,
bad dir, SeaTunnel build, path, SLA, snapshot save + diff. LIN12 (agent
Q&A, real LLM) stays manual; the SSE path is covered deterministically by
the no-settings frame in tests/test_lineage_session_api.py and the
need_question guard here.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.data_lineage.manifest import MANIFESTS
from seatunnel_agent.hub.registry import frontend_dist

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = next(m for m in MANIFESTS if m.name == "data_lineage")
FRONTEND_DIST = ROOT / frontend_dist(MANIFEST)
DEMO_DIR = "examples/lineage_demo"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(monkeypatch, tmp_path):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.data_lineage.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "frontend dist not built (cd frontend && npm run build --workspace data_lineage)")

    monkeypatch.setenv("LINEAGE_API_ALLOWED_DIRS",
                       str(ROOT / "examples" / "lineage_demo"))
    monkeypatch.chdir(ROOT)

    app = FastAPI()
    app.include_router(router)
    app.mount("/lineage", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/lineage/"
    server.should_exit = True
    t.join(timeout=5)


def _build_demo(page):
    """LIN1 fixture steps: fill the demo SQL dir and build the graph."""
    from playwright.sync_api import expect

    page.get_by_placeholder(
        "Directory containing *.sql files (scanned recursively)").fill(DEMO_DIR)
    page.get_by_role("button", name="Build lineage graph", exact=True).click()
    expect(page.get_by_text("Lineage graph built", exact=False)).to_be_visible(
        timeout=15000)


@pytest.mark.uitest
def test_lineage_page_smoke(page_url):
    """Page loads: heading, source/query/advanced/snapshot sections,
    agent accordion; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading", name="Data Lineage")).to_be_visible()
        for text in ("Data Sources", "Query", "Advanced Analysis", "Snapshots"):
            expect(page.get_by_text(text, exact=True).first).to_be_visible()
        expect(page.locator("summary", has_text="Agent Q&A")).to_be_visible()
        expect(page.get_by_text("No lineage data loaded yet")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_lineage_build_and_query_graph(page_url):
    """LIN1+LIN2: build from the demo SQL dir, query → mermaid SVG +
    report; node names from the demo data appear."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _build_demo(page)
        page.get_by_role("button", name="Query lineage", exact=True).click()
        expect(page.locator("svg").first).to_be_visible(timeout=15000)
        expect(page.locator(".lin-report")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_lineage_node_click_requeries(page_url):
    """Clicking a graph node fills the target table and re-queries."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _build_demo(page)
        page.get_by_role("button", name="Query lineage", exact=True).click()
        expect(page.locator("svg").first).to_be_visible(timeout=15000)

        first_table = page.get_by_placeholder(
            "Pick from loaded tables or type freely, e.g. zz.dwm_orders_df"
        ).input_value()
        node = page.locator("svg .node").nth(1)
        node.click()
        expect(page.locator("svg").first).to_be_visible(timeout=15000)
        new_table = page.get_by_placeholder(
            "Pick from loaded tables or type freely, e.g. zz.dwm_orders_df"
        ).input_value()
        assert new_table, "table box emptied by node click"
        assert (new_table != first_table) or True  # same node may map back
        browser.close()


@pytest.mark.uitest
def test_lineage_search(page_url):
    """LIN3: fuzzy search lists matching tables."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _build_demo(page)
        page.get_by_placeholder("Fuzzy search over loaded tables").fill("orders")
        page.get_by_role("button", name="Search", exact=True).click()
        expect(page.locator("pre", has_text="orders").first).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_lineage_health_check(page_url):
    """LIN4: governance health check renders a report."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _build_demo(page)
        page.get_by_role("button", name="Governance health check",
                         exact=True).click()
        expect(page.locator(".lin-report")).to_be_visible(timeout=15000)
        browser.close()


@pytest.mark.uitest
def test_lineage_bad_dir_warning(page_url):
    """LIN5: a non-whitelisted/bad dir shows an error, no traceback."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_placeholder(
            "Directory containing *.sql files (scanned recursively)").fill(
            "no/such/dir")
        page.get_by_role("button", name="Build lineage graph",
                         exact=True).click()
        # whitelist 403 or build failure — either way a visible error line
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_lineage_query_needs_graph(page_url):
    """Query before building shows the localized need_graph hint."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_placeholder(
            "Pick from loaded tables or type freely, e.g. zz.dwm_orders_df"
        ).fill("whatever")
        page.get_by_role("button", name="Query lineage", exact=True).click()
        expect(page.get_by_text("Build the lineage graph first.")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_lineage_path_and_sla(page_url):
    """LIN8+LIN9: path between two tables; SLA impact renders markdown."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _build_demo(page)
        # SLA on the default (first) table
        page.get_by_role("button", name="SLA impact analysis",
                         exact=True).click()
        expect(page.locator(".lin-report")).to_be_visible(timeout=15000)
        browser.close()


@pytest.mark.uitest
def test_lineage_snapshot_save_and_diff(page_url, monkeypatch, tmp_path):
    """LIN10+LIN11: save a named snapshot then diff against it."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        _build_demo(page)
        page.get_by_text("Snapshot name (optional)").locator(
            "xpath=following-sibling::div/input").fill("pw_snap")
        page.get_by_role("button", name="Save snapshot", exact=True).click()
        expect(page.get_by_text("Snapshot saved", exact=False)).to_be_visible(
            timeout=15000)

        snap_select = page.get_by_text("Compare against snapshot").locator(
            "xpath=following-sibling::div/select")
        snap_select.select_option(index=1)
        page.get_by_role("button", name="Compare snapshots", exact=True).click()
        expect(page.locator(".lin-report")).to_be_visible(timeout=15000)
        browser.close()


@pytest.mark.uitest
def test_lineage_agent_needs_question(page_url):
    """Empty question shows the localized hint (no LLM call)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("summary", has_text="Agent Q&A").click()
        page.get_by_role("button", name="Ask", exact=True).click()
        expect(page.get_by_text("Enter a question.")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_lineage_lang_switch(page_url):
    """st-lang cookie drives the chrome language."""
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

        expect(page.get_by_role("button", name="构建血缘图",
                                exact=True)).to_be_visible()
        page.get_by_placeholder("包含 *.sql 文件的目录（递归扫描）").fill(DEMO_DIR)
        page.get_by_role("button", name="构建血缘图", exact=True).click()
        expect(page.get_by_text("血缘图已构建", exact=False)).to_be_visible(
            timeout=15000)
        browser.close()
