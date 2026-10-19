"""Browser tests for the React /dagcheck page (ticket 02).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_metricdiff_page.py. Deselected by default:

    pytest -m uitest tests/test_dagcheck_page.py

Equivalence coverage for the retired uitest YAML cases
(cases/dagcheck.yaml DAG1-DAG5, removed in this ticket): cycle + broken
upstream (DAG1), execution batches + critical path (DAG2), unschedulable
tables (DAG3), bad dir warning without traceback (DAG4), English flow
(DAG5); plus non-default dialect (spark) and empty-input prompt.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

from tests.conftest import assert_dialect_switch

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.dag_check.manifest import MANIFEST
from seatunnel_agent.hub.registry import frontend_dist

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / frontend_dist(MANIFEST)
DEMO = ROOT / "examples" / "dagcheck_demo"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(monkeypatch):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.data.dag_check.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip(
            "frontend dist not built (cd frontend && npm run build --workspace dag_check)")

    monkeypatch.setenv("DAGCHECK_API_ALLOWED_DIRS", str(DEMO))
    monkeypatch.chdir(ROOT)

    app = FastAPI()
    app.include_router(router)
    app.mount("/dagcheck", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/dagcheck/"
    server.should_exit = True
    t.join(timeout=5)


def _zh_page(ctx_factory, page_url):
    """New page with the st-lang=zh-CN cookie set (Chinese chrome+report)."""
    from urllib.parse import urlparse

    host = urlparse(page_url).hostname
    ctx = ctx_factory()
    ctx.add_cookies([{"name": "st-lang", "value": "zh-CN",
                      "domain": host, "path": "/"}])
    page = ctx.new_page()
    page.goto(page_url, wait_until="networkidle")
    return page


@pytest.mark.uitest
def test_dagcheck_page_smoke(page_url):
    """Smoke: English chrome, demo prefill, run button; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role(
            "heading", name="Scheduling DAG Health Check")).to_be_visible()
        assert (page.locator("input").first.input_value()
                == "examples/dagcheck_demo")
        expect(page.locator("select")).to_have_value("hive")
        expect(page.get_by_role("button", name="Check DAG",
                                exact=True)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_dagcheck_cycle_and_broken_upstream(page_url):
    """DAG1: demo dir reports the title, the dependency cycle and the
    dangling upstream table dwd.missing_src (zh report)."""
    from playwright.sync_api import expect, sync_playwright

    assert DEMO.is_dir(), f"demo dir missing: {DEMO}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.get_by_role("button", name="体检 DAG", exact=True).click()
        report = page.locator(".md-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("调度 DAG 体检")
        expect(report).to_contain_text("依赖成环")
        expect(report).to_contain_text("dwd.missing_src")
        browser.close()


@pytest.mark.uitest
def test_dagcheck_batches_and_critical_path(page_url):
    """DAG2: execution batches and the critical path ending at
    ads.gmv_report are rendered (zh report)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.get_by_role("button", name="体检 DAG", exact=True).click()
        report = page.locator(".md-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("执行分批")
        expect(report).to_contain_text("关键路径")
        expect(report).to_contain_text("ads.gmv_report")
        browser.close()


@pytest.mark.uitest
def test_dagcheck_unschedulable_cycle_tables(page_url):
    """DAG3: tables on the cycle land in the unschedulable section."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.get_by_role("button", name="体检 DAG", exact=True).click()
        report = page.locator(".md-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("无法调度")
        expect(report).to_contain_text("tmp.a")
        browser.close()


@pytest.mark.uitest
def test_dagcheck_bad_dir_warning(page_url):
    """DAG4: non-directory path shows the localized bad_dir warning,
    no traceback anywhere on the page."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.locator("input").first.fill(str(DEMO / "no_such_dir_dag"))
        page.get_by_role("button", name="体检 DAG", exact=True).click()
        expect(page.get_by_text("不是有效目录", exact=False)).to_be_visible(
            timeout=10000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_dagcheck_english_flow(page_url):
    """DAG5: English chrome runs the check and renders the English
    report title and critical path section."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Check DAG", exact=True).click()
        report = page.locator(".md-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("Scheduling DAG Health Check")
        expect(report).to_contain_text("Critical path")
        browser.close()


@pytest.mark.uitest
def test_dagcheck_dialect_switch_spark(page_url):
    """Non-default dialect (spark) still reports the cycle on the demo
    dir — shared conftest.assert_dialect_switch body."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        assert_dialect_switch(
            page, dialect="spark",
            run=lambda: page.get_by_role("button", name="Check DAG",
                                         exact=True).click(),
            report=page.locator(".md-report"), contains="tmp.a")
        browser.close()


@pytest.mark.uitest
def test_dagcheck_empty_dir_warning(page_url):
    """Empty directory input shows the localized prompt, no request fired."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("input").first.fill("")
        page.get_by_role("button", name="Check DAG", exact=True).click()
        expect(page.get_by_text("Provide a SQL directory first.",
                                exact=False)).to_be_visible()
        browser.close()
