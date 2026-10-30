"""Browser tests for the React /freshness page.

Serves the built dist + API router in-process, modeled on
tests/test_dagcheck_page.py. Deselected by default:

    pytest -m uitest tests/test_freshness_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.data_freshness.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "freshness_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.data_freshness.api:router",
    "/freshness", chdir="root",
    env={"FRESHNESS_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_freshness_page_run_flow(page_url):
    """Demo prefill → Scan file → verdict report; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role(
            "heading", name="Data Freshness Monitor")).to_be_visible()
        assert (page.locator("input").first.input_value()
                == "examples/freshness_demo/updates.json")
        page.get_by_role("button", name="Scan file", exact=True).click()

        expect(page.get_by_role(
            "heading", name="Data Freshness Scan")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()
