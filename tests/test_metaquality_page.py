"""Browser tests for the React /metaquality page.

Serves the built dist + API router in-process, modeled on
tests/test_hygiene_page.py. Deselected by default:

    pytest -m uitest tests/test_metaquality_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.metadata_quality.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "governance_demo"

BAD_DDL = (
    "CREATE TABLE ods.user_log (uid BIGINT COMMENT 'id', "
    "pay_amount DOUBLE, birth_date STRING COMMENT 'b');"
)


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.metadata_quality.api:router",
    "/metaquality", chdir="root",
    env={"METAQUALITY_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_metaquality_page_smoke(page_url):
    """English chrome renders, demo dir prefilled, no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="Metadata Quality")).to_be_visible()
        expect(page.get_by_role("button", name="Check directory",
                                exact=True)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_metaquality_demo_dir(page_url):
    """Demo dir renders a conventions report through the UI."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Check directory",
                         exact=True).click()
        report = page.locator(".metaquality-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("Metadata Quality Report")
        browser.close()


@pytest.mark.uitest
def test_metaquality_paste_ddl(page_url):
    """Pasted DDL surfaces the money-on-float finding."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("summary").click()
        page.get_by_placeholder(
            "Paste CREATE TABLE statements…").fill(BAD_DDL)
        page.get_by_role("button", name="Check DDL", exact=True).click()

        report = page.locator(".metaquality-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("pay_amount")
        expect(report).to_contain_text("DECIMAL")
        browser.close()
