"""Browser tests for the React /grants page.

Serves the built dist + API router in-process, modeled on
tests/test_metaquality_page.py. Deselected by default:

    pytest -m uitest tests/test_grants_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.grant_scan.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "pii_demo"

SQL = (
    "CREATE TABLE dw.users (phone STRING COMMENT 'p');\n"
    "GRANT SELECT ON DATABASE dw TO PUBLIC;\n"
    "GRANT SELECT ON TABLE dw.users TO USER analyst;"
)


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.grant_scan.api:router",
    "/grants", chdir="root",
    env={"GRANTS_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_grants_page_smoke(page_url):
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
                                name="Grant Surface")).to_be_visible()
        expect(page.get_by_role("button", name="Scan directory",
                                exact=True)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_grants_paste_sql_reports_findings(page_url):
    """Pasted GRANTs surface the public grant and the PII linkage."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("summary").click()
        page.locator("textarea").fill(SQL)
        page.get_by_role("button", name="Scan SQL", exact=True).click()

        report = page.locator(".grants-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("Grant Surface Report")
        expect(report).to_contain_text("public grant")
        expect(report).to_contain_text("sensitive-table grant")
        browser.close()
