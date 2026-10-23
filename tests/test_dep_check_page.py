"""Browser smoke for the React /depcheck page.

Serves the built dist + API router in-process (uvicorn thread).
Deselected by default (needs a browser + built dist):

    pytest -m uitest tests/test_dep_check_page.py
"""

from __future__ import annotations

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.devops.dep_check.manifest import MANIFEST

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.devops.dep_check.api:router", "/depcheck")


@pytest.mark.uitest
def test_dep_check_page_smoke(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        # page loaded — header visible
        expect(page.get_by_text("Dependency Health")).to_be_visible()

        # paste text and click Analyze
        textarea = page.locator("textarea")
        expect(textarea).to_be_visible()
        textarea.fill("requests==2.31.0\nflask>=3.0")
        page.get_by_role("button", name="Analyze").click()

        # report appears (wait for API response)
        expect(page.locator("main")).to_contain_text("requests", timeout=30000)

        # Clear resets
        page.get_by_role("button", name="Clear").click()
        expect(textarea).to_have_value("")

        browser.close()
