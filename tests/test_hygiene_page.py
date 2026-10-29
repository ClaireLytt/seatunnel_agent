"""Browser tests for the React /hygiene page.

Serves the built dist + API router in-process, modeled on
tests/test_pii_page.py. Deselected by default:

    pytest -m uitest tests/test_hygiene_page.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.lineage_hygiene.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "pii_demo"

DEAD_SQL = (
    "CREATE TABLE ods.a (id BIGINT, unused STRING);\n"
    "CREATE TABLE dw.orphan (id BIGINT);\n"
    "INSERT INTO dw.orphan SELECT id FROM ods.a;"
)


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.lineage_hygiene.api:router",
    "/hygiene", chdir="root",
    env={"HYGIENE_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_hygiene_page_smoke(page_url):
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
                                name="Warehouse Hygiene")).to_be_visible()
        assert page.locator("input:not([type=checkbox])").input_value() \
            == "examples/pii_demo"
        expect(page.get_by_role("button", name="Analyze directory",
                                exact=True)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_hygiene_demo_dir_scan(page_url):
    """Demo dir reports its dead weight through the UI."""
    from playwright.sync_api import expect, sync_playwright

    assert DEMO.is_dir(), f"demo dir missing: {DEMO}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Analyze directory",
                         exact=True).click()
        report = page.locator(".hygiene-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("Hygiene Report")
        browser.close()


@pytest.mark.uitest
def test_hygiene_paste_sql(page_url):
    """Pasted SQL surfaces the orphan table and the dead column."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("summary").click()
        page.get_by_placeholder(
            "Paste CREATE TABLE / INSERT ... SELECT statements…").fill(DEAD_SQL)
        page.get_by_role("button", name="Analyze SQL", exact=True).click()

        report = page.locator(".hygiene-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("dw.orphan")
        expect(report).to_contain_text("unused")
        browser.close()
