"""Browser tests for the React /syncstrategy page.

Serves the built dist + API router in-process, modeled on
tests/test_dagcheck_page.py. Deselected by default:

    pytest -m uitest tests/test_syncstrategy_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.sync_strategy.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "syncstrategy_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.sync_strategy.api:router",
    "/syncstrategy", chdir="root",
    env={"SYNCSTRATEGY_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_syncstrategy_page_run_flow(page_url):
    """Demo prefill → Recommend from file → strategies + config stubs."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading", name="Sync Strategy",
                                exact=True)).to_be_visible()
        page.get_by_role("button", name="Recommend from file",
                         exact=True).click()

        expect(page.get_by_role(
            "heading", name="Sync Strategy Recommendation")).to_be_visible()
        expect(page.get_by_text("timestamp incremental",
                                exact=False).first).to_be_visible()
        expect(page.get_by_role(
            "heading", name="SeaTunnel job-config skeletons",
            exact=False)).to_be_visible()
        expect(page.get_by_text("MySQL-CDC",
                                exact=False).first).to_be_visible()
        # the schedule column renders both streaming and cron cadences
        expect(page.get_by_text("streaming (long-running)",
                                exact=False)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()
