"""Browser smoke for the React /release page.

Serves the built dist + API router in-process (uvicorn thread).
Deselected by default (needs a browser + built dist):

    pytest -m uitest tests/test_release_notes_page.py
"""

from __future__ import annotations

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.devops.release_notes.manifest import MANIFEST

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.devops.release_notes.api:router", "/release")


@pytest.mark.uitest
def test_release_notes_page_smoke(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        # page loaded — header visible
        expect(page.get_by_text("Release Notes")).to_be_visible()

        # paste commit log and click Generate
        textarea = page.locator("textarea")
        expect(textarea).to_be_visible()
        textarea.fill("a1b2c3d\tfeat(hub): new landing\nb2c3d4e\tfix: broken link")
        page.get_by_role("button", name="Generate").click()

        # report appears
        expect(page.locator("main")).to_contain_text("feat", timeout=30000)

        # Clear resets
        page.get_by_role("button", name="Clear").click()
        expect(textarea).to_have_value("")

        browser.close()
