"""Browser smoke for the React /doctor page.

Serves the built dist + API router in-process (uvicorn thread).
Uses the deterministic "Full check-up" button to avoid LLM dependency.
Deselected by default (needs a browser + built dist):

    pytest -m uitest tests/test_doctor_page.py
"""

from __future__ import annotations

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.devops.doctor.manifest import MANIFEST

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.devops.doctor.api:router", "/doctor")


@pytest.mark.uitest
def test_doctor_page_smoke(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        # page loaded — header visible
        expect(page.get_by_text("Environment Doctor")).to_be_visible()

        # Full check-up (deterministic, no LLM)
        page.get_by_role("button", name="Full check-up").click()

        # report appears with port/package info
        expect(page.locator("main")).to_contain_text("Packages", timeout=30000)

        # Clear resets
        page.get_by_role("button", name="Clear").click()
        expect(page.locator("textarea")).to_have_value("")

        browser.close()
