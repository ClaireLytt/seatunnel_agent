"""Browser tests for the React /duppipeline page.

Serves the built dist + API router in-process, modeled on
tests/test_sampleprofile_page.py. Deselected by default:

    pytest -m uitest tests/test_duppipeline_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.dup_pipeline.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "duppipeline_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.dup_pipeline.api:router",
    "/duppipeline", chdir="root",
    env={"DUPPIPELINE_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_duppipeline_page_run_flow(page_url):
    """Prefilled SQL → Detect duplicates → graded findings."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role(
            "heading", name="Dup Pipelines",
            exact=True).first).to_be_visible()
        page.get_by_role("button", name="Detect duplicates",
                         exact=True).click()

        expect(page.get_by_text("DP001", exact=False).first).to_be_visible()
        expect(page.get_by_text("dws.order_summary_bi",
                                exact=False).first).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


nokey_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.dup_pipeline.api:router",
    "/duppipeline", chdir="root", neutralize_llm=True,
    env={"DUPPIPELINE_API_ALLOWED_DIRS": str(DEMO)},
    name="nokey_url")


@pytest.mark.uitest
def test_duppipeline_note_without_key_surfaces_503(nokey_url):
    """LLM plan checked without a key -> inline 503, no crash."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(nokey_url, wait_until="networkidle")
        page.get_by_text("LLM consolidation plan", exact=False).click()
        page.get_by_role("button", name="Detect duplicates",
                         exact=True).click()
        expect(page.get_by_text("API_KEY is not set",
                                exact=False)).to_be_visible(timeout=15000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()
