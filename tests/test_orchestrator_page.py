"""Browser tests for the React /orchestrator page (ticket 04).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_dagcheck_page.py. Deselected by default:

    pytest -m uitest tests/test_orchestrator_page.py

Equivalence coverage for the retired uitest YAML case
(cases/aiplatform.yaml ORCH1, removed in this ticket): the routable-agent
panel lists sql_review / sql_fmt with the /sqlreview page link, no
traceback (ORCH1); plus English smoke (title, send/new-session buttons,
example fill), the no-LLM degraded suggestion reply, session restore
from the persisted chat log, and before/after screenshots.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.ai.orchestrator.manifest import MANIFEST
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

    from seatunnel_agent.agents.ai.orchestrator.api import router

    if not (FRONTEND_DIST / "index.html").is_file():
        pytest.skip("frontend dist not built "
                    "(cd frontend && npm run build --workspace "
                    "orchestrator-frontend)")

    # no .env in cwd + no key in env -> the chat endpoint degrades to
    # deterministic keyword suggestions (stable, no network)
    monkeypatch.chdir(tmp_path)
    for var in ("API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    # the user-level settings store must not re-inject a real key
    monkeypatch.setenv("SEATUNNEL_LLM_SETTINGS_PATH",
                       str(tmp_path / "no_settings.json"))
    # dotenv searches upward from the api module, so chdir alone cannot
    # hide the repo's .env — stub it (same seam as TestApi's no-key test)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr("seatunnel_agent.common.config.load_dotenv",
                        lambda *a, **k: None)
    monkeypatch.setenv("ORCH_CHAT_LOG", "1")
    monkeypatch.setenv("ORCH_CHAT_PATH", str(tmp_path / "chat.jsonl"))

    app = FastAPI()
    app.include_router(router)
    app.mount("/orchestrator",
              StaticFiles(directory=FRONTEND_DIST, html=True))

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
    yield f"http://127.0.0.1:{port}/orchestrator/"
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
def test_orchestrator_page_smoke(page_url):
    """Smoke: English chrome, chat controls, example fills the input;
    no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role(
            "heading", name="Agent Orchestrator")).to_be_visible()
        expect(page.get_by_role("button", name="Send",
                                exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="New session",
                                exact=True)).to_be_visible()

        page.get_by_role("button", name="Try: SQL review").click()
        assert "Review this SQL" in page.locator("textarea").input_value()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_orchestrator_agents_panel(page_url):
    """ORCH1 parity: the routable-agent panel lists sql_review / sql_fmt
    with the /sqlreview link; no traceback on the page (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.get_by_text("可路由的 agent").click()
        panel = page.locator("details").last
        expect(panel).to_contain_text("sql_review", timeout=10000)
        expect(panel).to_contain_text("sql_fmt")
        expect(panel.get_by_role("link", name="/sqlreview")).to_be_visible()
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_orchestrator_no_llm_suggests(page_url):
    """Without an LLM key the sent message degrades to keyword
    suggestions carrying the no-key notice (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.locator("textarea").fill("审查这段 SQL:SELECT 1")
        page.get_by_role("button", name="发送", exact=True).click()
        bot = page.locator(".st-msg-bot")
        expect(bot).to_be_visible(timeout=15000)
        expect(bot).to_contain_text("未配置 LLM")
        expect(bot).to_contain_text("sql_review")
        expect(page.locator(".st-msg-user")).to_contain_text("审查这段 SQL")
        browser.close()


@pytest.mark.uitest
def test_orchestrator_session_restore_and_clear(page_url, tmp_path):
    """A persisted session is rendered on load (with the tools-used
    note); New session clears it and the clear survives a reload."""
    from playwright.sync_api import expect, sync_playwright

    from seatunnel_agent.agents.ai.orchestrator.olog import ChatLogger
    lg = ChatLogger(tmp_path / "chat.jsonl")
    lg.log_turn("s1", "format this sql", "formatted ok",
                [{"tool": "sql_fmt", "elapsed_ms": 7}])

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        expect(page.locator(".st-msg-user")).to_contain_text(
            "format this sql")
        bot = page.locator(".st-msg-bot")
        expect(bot).to_contain_text("formatted ok")
        expect(bot).to_contain_text("sql_fmt")

        page.get_by_role("button", name="New session", exact=True).click()
        expect(page.locator(".st-msg-user")).to_have_count(0)
        page.reload(wait_until="networkidle")
        expect(page.locator(".st-msg-user")).to_have_count(0)
        browser.close()


@pytest.mark.uitest
def test_orchestrator_i18n_and_dark_screenshots(page_url):
    """en-dark and zh-light shots with the agents panel open, plus a
    zh suggestion round-trip shot (the after-side of the migration
    comparison in docs/reports/shots/)."""
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
        expect(page.get_by_role(
            "heading", name="Agent Orchestrator")).to_be_visible()
        page.get_by_text("Routable agents").click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOTS / "orchestrator-react-en-dark.png"),
                        full_page=True)
        ctx.close()

        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = _zh_page(lambda: ctx, page_url)
        expect(page.get_by_role("heading", name="智能编排")).to_be_visible()
        page.screenshot(path=str(SHOTS / "orchestrator-react-zh-light.png"),
                        full_page=True)

        page.locator("textarea").fill("审查这段 SQL:SELECT 1")
        page.get_by_role("button", name="发送", exact=True).click()
        expect(page.locator(".st-msg-bot")).to_be_visible(timeout=15000)
        page.get_by_text("可路由的 agent").click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOTS / "orchestrator-react-zh-chat.png"),
                        full_page=True)
        browser.close()
