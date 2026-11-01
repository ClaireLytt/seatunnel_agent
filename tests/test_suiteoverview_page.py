"""Browser tests for the React /suites navigator page.

A page-only plugin: the mounted router is a neighbor agent's (the page
itself calls no API). Deselected by default:

    pytest -m uitest tests/test_suiteoverview_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.suite_overview.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.sample_profile.api:router",
    "/suites", chdir="root")


@pytest.mark.uitest
def test_suiteoverview_page_renders(page_url):
    """All four suites render with their agent tiles and flow arrows."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role(
            "heading", name="Suite Overview",
            exact=True).first).to_be_visible()
        for tile in ("Sample Profiler", "Asset Search", "Kafka Lag",
                     "Task Failure"):
            expect(page.get_by_text(tile, exact=True)).to_be_visible()
        # a handoff arrow and a link target
        expect(page.get_by_text("Data Volatility → Quality Trace",
                                exact=False)).to_be_visible()
        href = page.get_by_text("Kafka Lag", exact=True).locator("xpath=..")
        assert (href.get_attribute("href") or "").endswith("/kafkalag/")

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()
