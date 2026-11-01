"""Browser tests for the React /backfill page.

Serves the built dist + API router in-process, modeled on
tests/test_dagcheck_page.py. Deselected by default:

    pytest -m uitest tests/test_backfill_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.backfill.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "backfill_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.backfill.api:router",
    "/backfill", chdir="root",
    env={"BACKFILL_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_backfill_page_run_flow(page_url):
    """Demo prefill → Plan file → batch plan; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role(
            "heading", name="Backfill Planner")).to_be_visible()
        assert (page.locator("input").first.input_value()
                == "examples/backfill_demo/updates.json")
        page.get_by_role("button", name="Plan file", exact=True).click()

        expect(page.get_by_role("heading", name="Backfill Plan",
                                exact=True)).to_be_visible()
        # the demo cascades ods.items through dws.sales to ads.sales_report
        expect(page.get_by_text("ods.items").first).to_be_visible()
        expect(page.get_by_text("ads.sales_report").first).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()
