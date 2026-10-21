"""Browser tests for the React /promptlab page (ticket 04).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_llmeval_page.py. Deselected by default:

    pytest -m uitest tests/test_promptlab_page.py

Equivalence coverage for the retired uitest YAML cases
(cases/aiplatform.yaml PLAB1-PLAB2, removed in this ticket): running
with an empty prompt shows the paste-first notice without firing a
request (PLAB1), refreshing the history panel renders without a
traceback (PLAB2); plus English smoke (controls, profiles load, no
console errors) and before/after screenshots.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.ai.prompt_lab.manifest import MANIFEST
from tests.conftest import make_page_url
from tests.conftest import zh_page as _zh_page

SHOTS = Path(__file__).resolve().parents[1] / "docs" / "reports" / "shots"

# experiment log must not leak between tests (history panel reads it)
page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.ai.prompt_lab.api:router",
    "/promptlab", env={"PROMPT_LAB_PATH": "{tmp}/xlog.jsonl"})


@pytest.mark.uitest
def test_promptlab_page_smoke(page_url):
    """Smoke: English chrome, controls, (active) profile preselected;
    no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading", name="Prompt Lab")).to_be_visible()
        expect(page.get_by_role("button", name="Run matrix",
                                exact=True)).to_be_visible()
        active = page.locator("input[type=checkbox]").first
        expect(active).to_be_checked()  # "(active)" preselected

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_promptlab_empty_prompt_notice(page_url):
    """PLAB1 parity: running with an empty prompt shows the paste-first
    notice and fires no /run request (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        requests: list[str] = []
        page.on("request", lambda r: requests.append(r.url)
                if r.url.endswith("/run") else None)

        page.get_by_role("button", name="运行对比", exact=True).click()
        expect(page.get_by_text("请先输入 Prompt")).to_be_visible(
            timeout=10000)
        assert not requests
        browser.close()


@pytest.mark.uitest
def test_promptlab_history_refresh(page_url):
    """PLAB2 parity: the history panel refreshes without a traceback;
    a fresh log shows the no-history notice (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.get_by_text("实验历史").click()
        page.get_by_role("button", name="刷新历史", exact=True).click()
        expect(page.get_by_text("还没有实验记录")).to_be_visible(
            timeout=10000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_promptlab_i18n_and_dark_screenshots(page_url):
    """en-dark and zh-light shots, plus the zh empty-prompt notice (the
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
        expect(page.get_by_role("heading", name="Prompt Lab")).to_be_visible()
        page.screenshot(path=str(SHOTS / "promptlab-react-en-dark.png"),
                        full_page=True)
        ctx.close()

        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = _zh_page(lambda: ctx, page_url)
        expect(page.get_by_role("heading",
                                name="Prompt 实验室")).to_be_visible()
        page.screenshot(path=str(SHOTS / "promptlab-react-zh-light.png"),
                        full_page=True)

        page.get_by_role("button", name="运行对比", exact=True).click()
        expect(page.get_by_text("请先输入 Prompt")).to_be_visible(
            timeout=10000)
        page.get_by_text("实验历史").click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOTS / "promptlab-react-zh-empty.png"),
                        full_page=True)
        browser.close()
