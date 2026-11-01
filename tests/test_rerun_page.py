"""Browser tests for the React /rerun page.

Serves the built dist + API router in-process, modeled on
tests/test_dagcheck_page.py. Deselected by default:

    pytest -m uitest tests/test_rerun_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.rerun_plan.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "rerun_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.rerun_plan.api:router",
    "/rerun", chdir="root",
    env={"RERUN_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_rerun_page_run_flow(page_url):
    """Demo prefill → Plan file → batches, ETA, untouched branches."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="Rerun Planner")).to_be_visible()
        assert (page.locator("input").nth(1).input_value()
                == "clean_orders")
        page.get_by_role("button", name="Plan file", exact=True).click()

        expect(page.get_by_role("heading", name="Rerun Plan",
                                exact=True)).to_be_visible()
        expect(page.get_by_text("blast radius 50%")).to_be_visible()
        expect(page.get_by_text("Estimated duration 4",
                                exact=False)).to_be_visible()
        expect(page.get_by_role(
            "heading", name="Untouched branches")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()
