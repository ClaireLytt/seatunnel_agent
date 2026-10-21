"""Browser tests for the React /llmeval page (ticket 04).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_orchestrator_page.py. Deselected by default:

    pytest -m uitest tests/test_llmeval_page.py

Equivalence coverage for the retired uitest YAML cases
(cases/aiplatform.yaml EVAL1-EVAL3, removed in this ticket): demo load
puts text2sql-golden in the editor (EVAL1), an invalid suite reports the
top-level-mapping error with no traceback (EVAL2), an empty suite asks
to paste one first (EVAL3); plus English smoke, validate round-trip,
the trend panel's no-runs notice, and before/after screenshots.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.ai.llm_eval.manifest import MANIFEST
from tests.conftest import make_page_url
from tests.conftest import zh_page as _zh_page

SHOTS = Path(__file__).resolve().parents[1] / "runs" / "shots"

# runs log must not leak between tests (trend panel reads it)
page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.ai.llm_eval.api:router",
    "/llmeval", env={"LLM_EVAL_PATH": "{tmp}/runs.jsonl"})


@pytest.mark.uitest
def test_llmeval_page_smoke(page_url):
    """Smoke: English chrome and all controls; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading", name="LLM Eval")).to_be_visible()
        for name in ("Load demo suite", "Validate suite (no LLM)",
                     "Run suite"):
            expect(page.get_by_role("button", name=name,
                                    exact=True)).to_be_visible()
        expect(page.locator("input[type=checkbox]")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_llmeval_demo_then_validate(page_url):
    """EVAL1 parity + validate: demo load fills the editor with
    text2sql-golden; validate reports the suite as valid (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.get_by_role("button", name="载入示例套件").click()
        expect(page.locator("textarea")).to_contain_text("")  # attached
        page.wait_for_function(
            "document.querySelector('textarea').value.includes"
            "('text2sql-golden')")

        page.get_by_role("button", name="校验套件(不调 LLM)").click()
        report = page.locator(".le-report")
        expect(report).to_be_visible(timeout=10000)
        expect(report).to_contain_text("套件合法")
        browser.close()


@pytest.mark.uitest
def test_llmeval_invalid_suite_error(page_url):
    """EVAL2 parity: `cases: 42` reports the top-level-mapping parse
    error on validate; no traceback anywhere (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.locator("textarea").fill("cases: 42")
        page.get_by_role("button", name="校验套件(不调 LLM)").click()
        report = page.locator(".le-report")
        expect(report).to_be_visible(timeout=10000)
        expect(report).to_contain_text("期望顶层")
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_llmeval_empty_suite_prompt(page_url):
    """EVAL3 parity: running (and validating) an empty suite asks to
    paste one first, without firing a request (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        requests: list[str] = []
        page.on("request", lambda r: requests.append(r.url)
                if "/api/llmeval/" in r.url else None)

        page.get_by_role("button", name="运行套件").click()
        expect(page.locator(".le-report")).to_contain_text("请先粘贴")
        assert not [u for u in requests if u.endswith("/run")]
        browser.close()


@pytest.mark.uitest
def test_llmeval_trend_no_runs(page_url):
    """The trend panel reports no logged runs on a fresh log (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.get_by_text("分数趋势").click()
        page.get_by_role("button", name="刷新趋势").click()
        expect(page.get_by_text("还没有评测运行记录")).to_be_visible(
            timeout=10000)
        browser.close()


@pytest.mark.uitest
def test_llmeval_i18n_and_dark_screenshots(page_url):
    """en-dark and zh-light shots, plus a zh demo+validate round-trip
    shot (the after-side of the migration comparison)."""
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
        expect(page.get_by_role("heading", name="LLM Eval")).to_be_visible()
        page.screenshot(path=str(SHOTS / "llmeval-react-en-dark.png"),
                        full_page=True)
        ctx.close()

        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = _zh_page(lambda: ctx, page_url)
        expect(page.get_by_role("heading", name="LLM 评测")).to_be_visible()
        page.screenshot(path=str(SHOTS / "llmeval-react-zh-light.png"),
                        full_page=True)

        page.get_by_role("button", name="载入示例套件").click()
        page.wait_for_function(
            "document.querySelector('textarea').value.includes"
            "('text2sql-golden')")
        page.get_by_role("button", name="校验套件(不调 LLM)").click()
        expect(page.locator(".le-report")).to_be_visible(timeout=10000)
        page.get_by_text("分数趋势").click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOTS / "llmeval-react-zh-validate.png"),
                        full_page=True)
        browser.close()
