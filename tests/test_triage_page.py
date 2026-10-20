"""Browser tests for the React /triage page (ticket 02).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_docqa_page.py. The no-key 503 path is deterministic (env +
.env + settings store all neutralized), so no LLM is needed. Deselected
by default:

    pytest -m uitest tests/test_triage_page.py

No uitest YAML cases existed for /triage, so nothing is retired;
coverage here is new: English smoke, the empty-title notice (no request
fired), the no-key 503 surfaced inline, and before/after screenshots.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.ai.issue_triage.manifest import MANIFEST
from seatunnel_agent.hub.registry import frontend_dist

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / frontend_dist(MANIFEST)
SHOTS = ROOT / "docs" / "reports" / "shots"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(monkeypatch, tmp_path):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.ai.issue_triage.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip("frontend dist not built "
                    "(cd frontend && npm run build --workspace "
                    "issue-triage-frontend)")

    # neutralize every key source so /run answers a deterministic 503
    # (same seam as tests/test_orchestrator_page.py)
    monkeypatch.chdir(tmp_path)
    for var in ("API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SEATUNNEL_LLM_SETTINGS_PATH",
                       str(tmp_path / "no_settings.json"))
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr("seatunnel_agent.common.config.load_dotenv",
                        lambda *a, **k: None)

    app = FastAPI()
    app.include_router(router)
    app.mount("/triage", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/triage/"
    server.should_exit = True
    t.join(timeout=5)


def _zh_page(ctx_factory, page_url):
    """New page with the st-lang=zh-CN cookie set (Chinese chrome)."""
    host = urlparse(page_url).hostname
    ctx = ctx_factory()
    ctx.add_cookies([{"name": "st-lang", "value": "zh-CN",
                      "domain": host, "path": "/"}])
    page = ctx.new_page()
    page.goto(page_url, wait_until="networkidle")
    return page


@pytest.mark.uitest
def test_triage_page_smoke(page_url):
    """Smoke: English chrome and controls; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.locator("h1")).to_contain_text("Issue Triage Agent")
        expect(page.get_by_role("button", name="Triage",
                                exact=True)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_triage_empty_title_notice(page_url):
    """Triaging with an empty title shows the type-first notice and
    fires no run request (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        requests: list[str] = []
        page.on("request", lambda r: requests.append(r.url)
                if r.url.endswith("/run") else None)

        page.get_by_role("button", name="分诊", exact=True).click()
        expect(page.get_by_text("请先输入标题")).to_be_visible(timeout=10000)
        assert not requests
        browser.close()


@pytest.mark.uitest
def test_triage_no_key_503_surfaced(page_url):
    """Without an LLM key the run answers 503 and the page shows the
    detail inline, no traceback (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.locator("input[type=text]").first.fill("Doris sink 写入丢数据")
        page.get_by_role("button", name="分诊", exact=True).click()
        expect(page.get_by_text("⚠️", exact=False)).to_be_visible(
            timeout=15000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_triage_i18n_and_dark_screenshots(page_url):
    """en-dark and zh-light shots, plus the zh empty-title notice (the
    after-side of the migration comparison)."""
    from playwright.sync_api import expect, sync_playwright

    SHOTS.mkdir(parents=True, exist_ok=True)
    host = urlparse(page_url).hostname

    with sync_playwright() as p:
        browser = p.chromium.launch()

        ctx = browser.new_context(viewport={"width": 1280, "height": 900},
                                  color_scheme="dark")
        ctx.add_cookies([{"name": "st-lang", "value": "en",
                          "domain": host, "path": "/"}])
        page = ctx.new_page()
        page.goto(page_url, wait_until="networkidle")
        expect(page.locator("h1")).to_contain_text("Issue Triage Agent")
        page.screenshot(path=str(SHOTS / "triage-react-en-dark.png"),
                        full_page=True)
        ctx.close()

        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = _zh_page(lambda: ctx, page_url)
        expect(page.locator("h1")).to_contain_text("Issue 分诊 Agent")
        page.screenshot(path=str(SHOTS / "triage-react-zh-light.png"),
                        full_page=True)

        page.get_by_role("button", name="分诊", exact=True).click()
        expect(page.get_by_text("请先输入标题")).to_be_visible(timeout=10000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(SHOTS / "triage-react-zh-empty.png"),
                        full_page=True)
        browser.close()
