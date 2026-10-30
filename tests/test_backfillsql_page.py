"""Browser tests for the React /backfillsql page.

Serves the built dist + API router in-process, modeled on
tests/test_dagcheck_page.py. Deselected by default:

    pytest -m uitest tests/test_backfillsql_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.backfill_sql.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "backfillsql_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.backfill_sql.api:router",
    "/backfillsql", chdir="root",
    env={"BACKFILLSQL_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_backfillsql_page_run_flow(page_url):
    """Demo prefill → Generate from file → statements + reconciliation."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading", name="Backfill SQL",
                                exact=True).first).to_be_visible()
        page.get_by_role("button", name="Generate from file",
                         exact=True).click()

        expect(page.get_by_role(
            "heading", name="Pre-flight checks", exact=False)).to_be_visible()
        expect(page.get_by_role(
            "heading", name="Backfill statements",
            exact=False)).to_be_visible()
        expect(page.get_by_role(
            "heading", name="Reconciliation", exact=False)).to_be_visible()
        expect(page.get_by_text("INSERT OVERWRITE TABLE dws.sales",
                                exact=False).first).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_backfillsql_page_plan_to_specs(page_url):
    """The plan accordion turns planner JSON into per-table specs."""
    from playwright.sync_api import expect, sync_playwright

    plan = ('{"tables": [{"table": "dws.sales", '
            '"missing": ["2024-05-05"], "cascade": ["2024-05-04"]}]}')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_text("Specs from a backfill plan").click()
        page.locator("textarea").nth(1).fill(plan)
        page.get_by_role("button", name="Specs from plan",
                         exact=True).click()

        expect(page.get_by_role(
            "heading", name="Backfill spec skeletons",
            exact=False)).to_be_visible()
        expect(page.get_by_text("2024-05-04",
                                exact=False).first).to_be_visible()
        browser.close()
