"""Browser tests for the React /sqlperf page.

Serves the built dist + API router in-process, modeled on
tests/test_dagcheck_page.py. Deselected by default:

    pytest -m uitest tests/test_sqlperf_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.sql_perf.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "sqlperf_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.sql_perf.api:router",
    "/sqlperf", chdir="root",
    env={"SQLPERF_API_ALLOWED_DIRS": str(DEMO)})

nokey_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.sql_perf.api:router",
    "/sqlperf", chdir="root", neutralize_llm=True,
    env={"SQLPERF_API_ALLOWED_DIRS": str(DEMO)},
    name="nokey_url")


@pytest.mark.uitest
def test_sqlperf_rewrite_without_key_surfaces_503(nokey_url):
    """SQL pasted + rewrite checked, no key → inline 503, no crash."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(nokey_url, wait_until="networkidle")
        page.get_by_text("LLM rewrite of the SQL", exact=False).click()
        page.locator("textarea").nth(1).fill("SELECT * FROM ods.orders")
        page.get_by_text("Draft the optimized SQL", exact=False).click()
        page.get_by_role("button", name="Analyze file", exact=True).click()
        expect(page.get_by_text("API_KEY is not set",
                                exact=False)).to_be_visible(timeout=15000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_sqlperf_rewrite_needs_sql(page_url):
    """Checkbox on with an empty SQL box → inline hint, no request."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        page.get_by_text("LLM rewrite of the SQL", exact=False).click()
        page.get_by_text("Draft the optimized SQL", exact=False).click()
        page.get_by_role("button", name="Analyze file", exact=True).click()
        expect(page.get_by_text("Paste the original SQL first",
                                exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_sqlperf_page_run_flow(page_url):
    """Demo prefill → Analyze file → findings + scans; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="Plan Analyzer")).to_be_visible()
        assert (page.locator("input").first.input_value()
                == "examples/sqlperf_demo/plan.txt")
        page.get_by_role("button", name="Analyze file", exact=True).click()

        expect(page.get_by_role(
            "heading", name="Execution Plan Analysis")).to_be_visible()
        expect(page.get_by_text("PF002", exact=True)).to_be_visible()
        expect(page.get_by_role("heading", name="Scans")).to_be_visible()
        expect(page.get_by_text("ods.orders").first).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()
