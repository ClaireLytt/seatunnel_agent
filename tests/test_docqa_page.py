"""Browser tests for the React /docqa page (ticket 02).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_llmcost_page.py. The extractive path is deterministic (BM25
over the connector docs + repo docs), so no LLM is needed. Deselected by
default:

    pytest -m uitest tests/test_docqa_page.py

No uitest YAML cases existed for /docqa, so nothing is retired; coverage
here is new: English smoke, a deterministic extractive answer with
sources, the empty-question notice (no request fired), and before/after
screenshots.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.ai.doc_qa.manifest import MANIFEST
from tests.conftest import make_page_url
from tests.conftest import zh_page as _zh_page

SHOTS = Path(__file__).resolve().parents[1] / "runs" / "shots"

# the BM25 corpus reads docs/ relative to cwd -> chdir to the repo root
page_url = make_page_url(MANIFEST, "seatunnel_agent.agents.ai.doc_qa.api:router",
                         "/docqa", chdir="root")


@pytest.mark.uitest
def test_docqa_page_smoke(page_url):
    """Smoke: English chrome and controls; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.locator("h1")).to_have_text("Doc Q&A")
        expect(page.get_by_role("button", name="Ask",
                                exact=True)).to_be_visible()
        expect(page.locator("input[type=checkbox]")).not_to_be_checked()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_docqa_extractive_answer_with_sources(page_url):
    """A jdbc question returns the extractive report with a sources
    section — deterministic, no LLM (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.locator("textarea").fill("jdbc sink 怎么配置?")
        page.get_by_role("button", name="提问", exact=True).click()
        report = page.locator(".dq-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("jdbc", ignore_case=True)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_docqa_empty_question_notice(page_url):
    """Asking with an empty question shows the type-first notice and
    fires no ask request (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        requests: list[str] = []
        page.on("request", lambda r: requests.append(r.url)
                if r.url.endswith("/ask") else None)

        page.get_by_role("button", name="提问", exact=True).click()
        expect(page.get_by_text("请先输入问题")).to_be_visible(timeout=10000)
        assert not requests
        browser.close()


@pytest.mark.uitest
def test_docqa_i18n_and_dark_screenshots(page_url):
    """en-dark and zh-light shots, plus the zh answer round-trip (the
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
        expect(page.locator("h1")).to_have_text("Doc Q&A")
        page.screenshot(path=str(SHOTS / "docqa-react-en-dark.png"),
                        full_page=True)
        ctx.close()

        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = _zh_page(lambda: ctx, page_url)
        expect(page.locator("h1")).to_have_text("文档问答")
        page.screenshot(path=str(SHOTS / "docqa-react-zh-light.png"),
                        full_page=True)

        page.locator("textarea").fill("jdbc sink 怎么配置?")
        page.get_by_role("button", name="提问", exact=True).click()
        expect(page.locator(".dq-report")).to_be_visible(timeout=15000)
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOTS / "docqa-react-zh-answer.png"),
                        full_page=True)
        browser.close()
