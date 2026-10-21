"""Browser smoke for the React /seatunnel page (walking skeleton).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_uitest_page.py. Deselected by default (needs a browser +
built dist):

    pytest -m uitest tests/test_seatunnel_page.py
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.seatunnel.manifest import MANIFEST


class _FakePageAgent:
    """Scripted agent for browser tests: streams a short reply via on_event."""

    def __init__(self, settings, on_event=None):
        import threading as _threading

        self._on_event = on_event
        self.stop_event = _threading.Event()

    def set_event_callback(self, on_event) -> None:
        self._on_event = on_event

    def _turn(self, text: str) -> None:
        for chunk in (text[: len(text) // 2], text[len(text) // 2:]):
            self._on_event("text_delta", {"text": chunk})
            time.sleep(0.05)
        self._on_event("text", {"text": text})
        self._on_event("final_answer", {"text": text})

    def run(self, task: str) -> str:
        self._turn("Streamed hello from the agent")
        return ""

    def chat(self, message: str) -> str:
        self._turn("Second turn reply")
        return ""


@pytest.fixture(autouse=True)
def _fake_seatunnel_backend(monkeypatch, tmp_path):
    """Scripted agent + isolated history/conversation state (the server
    comes from the shared make_page_url factory; these module attrs are
    read per-request)."""
    from seatunnel_agent.agents.data.seatunnel import api
    from seatunnel_agent.common import history

    monkeypatch.setattr(history, "HISTORY_DIR", tmp_path)
    monkeypatch.setattr(history, "_OLD_HISTORY_DIR", tmp_path / "_old")
    monkeypatch.setattr(api, "SeaTunnelAgent", _FakePageAgent)
    monkeypatch.setattr(api, "load_settings", lambda: object())
    api._CONVERSATIONS.clear()
    api.CONNECTION.update({"settings": None, "version": None})


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.seatunnel.api:router", "/seatunnel")


@pytest.mark.uitest
def test_seatunnel_page_smoke(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        # shell rendered; backend meta reached the header badge
        expect(page.get_by_role("heading",
                                name="SeaTunnel Pipeline Builder")).to_be_visible()
        expect(page.locator(".st-sidebar")).to_be_visible()
        expect(page.locator(".st-chat input:not([type=file])")).to_be_visible()
        expect(page.locator("header")).to_contain_text("×4")

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_seatunnel_empty_placeholder_hints(page_url):
    """Legacy _build_placeholder parity: hint cards render in the empty
    chat and clicking one fills the input (ui.py hint-card delegation)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        expect(page.locator(".st-empty-state")).to_be_visible()
        expect(page.locator(".st-hint-card")).to_have_count(3)
        expect(page.locator(".st-docs-link")).to_be_visible()

        page.locator(".st-hint-card").first.click()
        expect(page.locator(".st-chat input:not([type=file])")).to_have_value(
            "Generate 10 fake rows to console")
        browser.close()


@pytest.mark.uitest
def test_seatunnel_chat_roundtrip(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        chat_input = page.locator(".st-chat input:not([type=file])")
        chat_input.fill("build me a pipeline")
        chat_input.press("Enter")

        # user bubble + streamed assistant reply + completion trailer
        # generous timeouts: the first rendered event lazily imports the
        # legacy ui module (gradio) in this bare test server; the real hub
        # imports it at startup
        expect(page.locator(".st-msg-user")).to_contain_text("build me a pipeline")
        expect(page.locator(".st-msg-bot").first).to_contain_text(
            "Streamed hello from the agent", timeout=20000)
        expect(page.locator(".st-msg-bot").last).to_contain_text(
            "Completed in", timeout=20000)
        # Send button is back after the stream ends
        expect(page.locator(".st-btn-send")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_seatunnel_sessions_sidebar(page_url):
    """Exchange persists to the sidebar; new chat resets; clicking restores."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        chat_input = page.locator(".st-chat input:not([type=file])")
        chat_input.fill("remember this chat")
        chat_input.press("Enter")
        expect(page.locator(".st-msg-bot").last).to_contain_text(
            "Completed in", timeout=20000)

        # the completed exchange shows up in the session list
        item = page.locator(".st-session-item")
        expect(item.first).to_contain_text("remember this chat", timeout=10000)

        # new chat clears the conversation
        page.locator(".st-new-chat").click()
        expect(page.locator(".st-msg-user")).to_have_count(0)

        # selecting the history entry restores its messages
        item.first.click()
        expect(page.locator(".st-msg-user")).to_contain_text("remember this chat")
        expect(page.locator(".st-msg-bot").first).to_contain_text(
            "Streamed hello from the agent")

        # sidebar collapse/expand toggle
        page.locator(".st-sidebar-toggle").click()
        expect(page.locator(".st-sidebar")).to_be_hidden()
        page.locator(".st-sidebar-toggle").click()
        expect(page.locator(".st-sidebar")).to_be_visible()
        browser.close()


SHOTS = Path(__file__).resolve().parents[1] / "docs" / "reports" / "shots"


@pytest.mark.uitest
def test_seatunnel_i18n_and_dark_screenshots(page_url):
    """zh via st-lang cookie covers sidebar/chat/controls; light+dark shots."""
    from urllib.parse import urlparse

    from playwright.sync_api import expect, sync_playwright

    SHOTS.mkdir(parents=True, exist_ok=True)
    host = urlparse(page_url).hostname

    def shot(page, name):
        page.screenshot(path=str(SHOTS / f"seatunnel-react-{name}.png"),
                        full_page=True)

    def element_shot(page, selector, name):
        page.locator(selector).screenshot(
            path=str(SHOTS / f"seatunnel-react-{name}.png"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(page_url, wait_until="networkidle")

        # populate the chat so message bubbles appear in the shots
        chat_input = page.locator(".st-chat input:not([type=file])")
        chat_input.fill("show me streaming output")
        chat_input.press("Enter")
        expect(page.locator(".st-msg-bot").last).to_contain_text(
            "Completed in", timeout=20000)

        for scheme in ("light", "dark"):
            page.emulate_media(color_scheme=scheme)
            shot(page, f"{scheme}-full")
            element_shot(page, ".st-sidebar", f"{scheme}-sidebar")
            element_shot(page, ".st-chat", f"{scheme}-chat")

        # zh: language follows the st-lang cookie (shared lang.ts)
        page.context.add_cookies(
            [{"name": "st-lang", "value": "zh", "domain": host, "path": "/"}])
        page.emulate_media(color_scheme="light")
        page.goto(page_url, wait_until="networkidle")
        expect(page.get_by_role("heading",
                                name="SeaTunnel \u6570\u636e\u7ba1\u9053\u6784\u5efa\u5668")).to_be_visible()
        expect(page.locator(".st-sidebar")).to_contain_text("\u5386\u53f2\u8bb0\u5f55")
        expect(page.locator(".st-sidebar")).to_contain_text("\u8fd0\u884c\u6a21\u5f0f")
        expect(page.locator(".st-sidebar")).to_contain_text("\u672a\u8fde\u63a5")
        expect(page.locator(".st-chat input:not([type=file])")
               ).to_have_attribute("placeholder",
                                   "\u8f93\u5165\u4f60\u7684\u6570\u636e\u7ba1\u9053\u4efb\u52a1...")
        shot(page, "light-zh-full")
        page.emulate_media(color_scheme="dark")
        shot(page, "dark-zh-full")
        browser.close()
