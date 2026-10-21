"""Browser tests for the React /llmcost page (ticket 04).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_promptlab_page.py, with the demo usage log + pricing
override so every number is deterministic. Deselected by default:

    pytest -m uitest tests/test_llmcost_page.py

Equivalence coverage for the retired uitest YAML cases
(cases/aiplatform.yaml COST1-COST3, removed in this ticket): the page
renders the cost report without a traceback (COST1), the price catalog
lists deepseek-chat with the prefix column (COST2), switching the window
to 7 days re-renders the 7-day report (COST3); plus English smoke, the
over-budget banner, and before/after screenshots.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.ai.llm_cost.manifest import MANIFEST
from tests.conftest import make_page_url
from tests.conftest import zh_page as _zh_page

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "reports" / "shots"
DEMO = ROOT / "examples" / "llmcost_demo"

# demo usage log + pricing override -> every number is deterministic
page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.ai.llm_cost.api:router", "/llmcost",
    env={"LLM_USAGE_PATH": str(DEMO / "llm_usage_sample.jsonl"),
         "SEATUNNEL_PRICING_PATH": str(DEMO / "pricing.yaml")})


@pytest.mark.uitest
def test_llmcost_page_smoke(page_url):
    """Smoke: English chrome, controls, auto-loaded report; no console
    errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.locator("h1")).to_have_text("LLM Cost")
        expect(page.get_by_role("button", name="Refresh",
                                exact=True)).to_be_visible()
        expect(page.locator("select")).to_have_value("30")
        expect(page.locator(".lc-report")).to_be_visible(timeout=10000)

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_llmcost_report_no_traceback(page_url):
    """COST1 parity: the zh report renders the cost title, no traceback
    anywhere on the page."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        report = page.locator(".lc-report")
        expect(report).to_be_visible(timeout=10000)
        expect(report).to_contain_text("LLM 成本")
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_llmcost_price_catalog(page_url):
    """COST2 parity: the price panel lists deepseek-chat under the
    prefix column (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.locator("details summary").last.click()
        panel = page.locator("details").last
        expect(panel).to_contain_text("模型前缀", timeout=10000)
        expect(panel).to_contain_text("deepseek-chat")
        browser.close()


@pytest.mark.uitest
def test_llmcost_window_switch(page_url):
    """COST3 parity: switching the window to 7 days re-renders the
    7-day report (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        expect(page.locator(".lc-report")).to_be_visible(timeout=10000)
        page.locator("select").select_option("7")
        expect(page.locator(".lc-report")).to_contain_text(
            "近 7 天", timeout=10000)
        browser.close()


@pytest.mark.uitest
def test_llmcost_over_budget_banner(page_url):
    """A tiny budget flips the over-budget banner on (zh)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        expect(page.locator(".lc-report")).to_be_visible(timeout=10000)
        page.locator("input[type=number]").fill("0.0001")
        expect(page.get_by_text("超出预算")).to_be_visible(timeout=10000)
        browser.close()


@pytest.mark.uitest
def test_llmcost_i18n_and_dark_screenshots(page_url):
    """en-dark and zh-light shots with charts, plus the zh price panel
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
        expect(page.locator(".lc-report")).to_be_visible(timeout=10000)
        page.wait_for_timeout(800)  # charts animate in
        page.screenshot(path=str(SHOTS / "llmcost-react-en-dark.png"),
                        full_page=True)
        ctx.close()

        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = _zh_page(lambda: ctx, page_url)
        expect(page.locator(".lc-report")).to_be_visible(timeout=10000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(SHOTS / "llmcost-react-zh-light.png"),
                        full_page=True)

        page.locator("details summary").last.click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(SHOTS / "llmcost-react-zh-prices.png"),
                        full_page=True)
        browser.close()
