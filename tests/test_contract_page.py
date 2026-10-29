"""Browser tests for the React /contract page.

Serves the built dist + API router in-process, modeled on
tests/test_metaquality_page.py. Deselected by default:

    pytest -m uitest tests/test_contract_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.contract_check.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "pii_demo"

CONTRACT = (
    "tables:\n"
    "  - name: dwd.orders\n"
    "    columns:\n"
    "      - { name: order_id, type: bigint }\n"
    "    partitioned_by: [dt]\n"
)

DDL = (
    "CREATE TABLE dwd.orders (order_id STRING COMMENT 'id') "
    "PARTITIONED BY (ds STRING COMMENT 'p');"
)


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.contract_check.api:router",
    "/contract", chdir="root",
    env={"CONTRACT_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_contract_page_smoke(page_url):
    """English chrome renders, contract field present, no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="Data Contract")).to_be_visible()
        expect(page.get_by_role("button", name="Check directory",
                                exact=True)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_contract_requires_yaml_first(page_url):
    """Clicking without a contract shows the inline nudge, no request."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Check directory",
                         exact=True).click()
        expect(page.get_by_text(
            "Paste the YAML contract first.")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_contract_paste_ddl_reports_violations(page_url):
    """Contract + pasted DDL surfaces the graded violations."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").first.fill(CONTRACT)
        page.locator("summary").click()
        page.get_by_placeholder(
            "Paste CREATE TABLE statements…").fill(DDL)
        page.get_by_role("button", name="Check DDL", exact=True).click()

        report = page.locator(".contract-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("Data Contract Report")
        expect(report).to_contain_text("type violation")
        expect(report).to_contain_text("partition violation")
        browser.close()
