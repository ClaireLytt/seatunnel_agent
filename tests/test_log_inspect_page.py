"""Browser smoke for the React /loginspect page.

Serves the built dist + API router in-process (uvicorn thread).
Uses directory scan against examples/logs_demo (deterministic, no LLM).
Deselected by default (needs a browser + built dist):

    pytest -m uitest tests/test_log_inspect_page.py
"""

from __future__ import annotations

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.log_inspect.manifest import MANIFEST

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.log_inspect.api:router", "/loginspect",
    chdir="root")


@pytest.mark.uitest
def test_log_inspect_page_smoke(page_url):
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        # page loaded — header visible
        expect(page.get_by_text("Batch Log Inspection")).to_be_visible()

        # directory input pre-filled, click Inspect
        page.get_by_role("button", name="Inspect directory").click()

        # report appears with cluster info
        expect(page.locator("main")).to_contain_text("ConnectException", timeout=30000)

        # Clear resets
        page.get_by_role("button", name="Clear").click()

        browser.close()
