"""Browser tests for the React /webtask page (ticket 03).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_codefix_page.py. WEBTASK_API_ENABLED stays unset here, so
the run endpoint answers 403 — a deterministic path that starts no
Playwright session and needs no LLM. Deselected by default:

    pytest -m uitest tests/test_webtask_page.py

No uitest YAML cases existed for /webtask, so nothing is retired;
coverage here is new: English smoke, the empty-goal notice (no request
fired), the 403 default-off refusal surfaced inline, and before/after
screenshots.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.ai.web_task.manifest import MANIFEST
from seatunnel_agent.hub.registry import frontend_dist

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / frontend_dist(MANIFEST)
SHOTS = ROOT / "docs" / "reports" / "shots"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def page_url(monkeypatch):
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from seatunnel_agent.agents.ai.web_task.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip("frontend dist not built "
                    "(cd frontend && npm run build --workspace "
                    "web-task-frontend)")

    # gate unset -> the run endpoint answers 403 (the default-off
    # posture this page must surface clearly)
    monkeypatch.delenv("WEBTASK_API_ENABLED", raising=False)

    app = FastAPI()
    app.include_router(router)
    app.mount("/webtask", StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/webtask/"
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
def test_webtask_page_smoke(page_url):
    """Smoke: English chrome, controls, hub default URL prefilled; no
    console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.locator("h1")).to_contain_text("Web Task Agent")
        expect(page.get_by_role("button", name="Run task",
                                exact=True)).to_be_visible()
        assert (page.locator("input[type=text]").first.input_value()
                == "http://127.0.0.1:7860/")
        expect(page.locator("input[type=range]")).to_have_value("15")

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_webtask_empty_goal_notice(page_url):
    """Running with an empty goal shows the fill-first notice and fires
    no run request (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        requests: list[str] = []
        page.on("request", lambda r: requests.append(r.url)
                if r.url.endswith("/run") else None)

        page.get_by_role("button", name="执行任务", exact=True).click()
        expect(page.get_by_text("请先填写目标与 URL")).to_be_visible(
            timeout=10000)
        assert not requests
        browser.close()


@pytest.mark.uitest
def test_webtask_disabled_403_surfaced(page_url):
    """With the gate unset the run endpoint answers 403 and the page
    shows the refusal inline, no traceback (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.locator("textarea").fill("打开首页")
        page.get_by_role("button", name="执行任务", exact=True).click()
        expect(page.get_by_text("WEBTASK_API_ENABLED",
                                exact=False)).to_be_visible(timeout=10000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_webtask_i18n_and_dark_screenshots(page_url):
    """en-dark and zh-light shots, plus the zh 403 refusal round-trip
    (the after-side of the migration comparison)."""
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
        expect(page.locator("h1")).to_contain_text("Web Task Agent")
        page.screenshot(path=str(SHOTS / "webtask-react-en-dark.png"),
                        full_page=True)
        ctx.close()

        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = _zh_page(lambda: ctx, page_url)
        expect(page.locator("h1")).to_contain_text("网页操作 Agent")
        page.screenshot(path=str(SHOTS / "webtask-react-zh-light.png"),
                        full_page=True)

        page.locator("textarea").fill("打开首页")
        page.get_by_role("button", name="执行任务", exact=True).click()
        expect(page.get_by_text("WEBTASK_API_ENABLED",
                                exact=False)).to_be_visible(timeout=10000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(SHOTS / "webtask-react-zh-403.png"),
                        full_page=True)
        browser.close()
