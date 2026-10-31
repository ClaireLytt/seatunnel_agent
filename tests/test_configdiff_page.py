"""Browser tests for the React /configdiff page.

Serves the built dist + API router in-process, modeled on
tests/test_sampleprofile_page.py. Deselected by default:

    pytest -m uitest tests/test_configdiff_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.config_diff.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "configdiff_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.config_diff.api:router",
    "/configdiff", chdir="root",
    env={"CONFIGDIFF_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_configdiff_page_run_flow(page_url):
    """Prefilled configs → Diff → graded differences."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role(
            "heading", name="Config Diff", exact=True).first).to_be_visible()
        page.get_by_role("button", name="Diff", exact=True).click()

        expect(page.get_by_text("env.parallelism",
                                exact=False).first).to_be_visible()
        expect(page.get_by_text("***", exact=False).first).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


nokey_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.config_diff.api:router",
    "/configdiff", chdir="root", neutralize_llm=True,
    env={"CONFIGDIFF_API_ALLOWED_DIRS": str(DEMO)},
    name="nokey_url")


@pytest.mark.uitest
def test_configdiff_note_without_key_surfaces_503(nokey_url):
    """LLM review checked without a key -> inline 503, no crash."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(nokey_url, wait_until="networkidle")
        page.get_by_text("LLM drift review", exact=False).click()
        page.get_by_role("button", name="Diff", exact=True).click()
        expect(page.get_by_text("API_KEY is not set",
                                exact=False)).to_be_visible(timeout=15000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()
