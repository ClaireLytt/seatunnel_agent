"""Browser tests for the React /ddlguard page.

Serves the built dist + API router in-process, modeled on
tests/test_metaquality_page.py. Deselected by default:

    pytest -m uitest tests/test_ddlguard_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.ddl_guard.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "governance_demo"

MIGRATION = (
    "CREATE TABLE dw.orders (legacy_flag INT COMMENT 'l');\n"
    "ALTER TABLE dw.orders DROP COLUMN legacy_flag;\n"
    "DROP TABLE dw.retired_tmp;"
)


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.ddl_guard.api:router",
    "/ddlguard", chdir="root",
    env={"DDLGUARD_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_ddlguard_page_smoke(page_url):
    """English chrome renders, no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="Migration Guard")).to_be_visible()
        expect(page.get_by_role("button", name="Guard SQL",
                                exact=True)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_ddlguard_paste_migration_reports_rollback(page_url):
    """Pasted migration surfaces graded drops and the rollback script."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").fill(MIGRATION)
        page.get_by_role("button", name="Guard SQL", exact=True).click()

        report = page.locator(".ddlguard-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("Migration Guard Report")
        expect(report).to_contain_text("drop column")
        expect(report).to_contain_text("Rollback script")
        expect(report).to_contain_text("ADD COLUMNS (legacy_flag INT)")
        browser.close()
