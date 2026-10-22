"""Browser tests for the React /schemadrift page (ticket 02).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_sqlfmt_page.py. Deselected by default:

    pytest -m uitest tests/test_schemadrift_page.py

Equivalence coverage for the retired uitest YAML cases
(cases/schemadrift.yaml SDF1-SDF6, removed in this ticket): dirs demo
compare, pasted-DDL drift (drop column + widen type), identical schemas,
suspected rename, bad path warning, English flow.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import assert_dialect_switch, make_page_url
from tests.conftest import zh_page as _zh_page

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.schema_drift.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "schema_drift_demo"

OLD_DDL = ("CREATE TABLE t (id BIGINT, phone STRING, amount DECIMAL(10,2))")
NEW_DDL = ("CREATE TABLE t (id BIGINT, amount DECIMAL(16,2))")
RENAME_OLD = "CREATE TABLE t (id BIGINT, user_name STRING)"
RENAME_NEW = "CREATE TABLE t (id BIGINT, user_real_name STRING)"


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.schema_drift.api:router",
    "/schemadrift", chdir="root",
    env={"SCHEMADRIFT_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_schemadrift_page_smoke(page_url):
    """SDF6-adjacent: English chrome, controls, demo prefill; no console
    errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="Schema Drift Check")).to_be_visible()
        expect(page.locator("select")).to_have_value("hive")
        expect(page.get_by_role("button", name="Compare",
                                exact=True)).to_be_visible()
        page.locator("summary").click()
        expect(page.get_by_text("Old directory / file")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_schemadrift_dirs_demo(page_url):
    """SDF1: demo directories compare to the graded drift report."""
    from playwright.sync_api import expect, sync_playwright

    assert DEMO.is_dir(), f"demo dir missing: {DEMO}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("summary").click()
        page.get_by_role("button", name="Compare directories",
                         exact=True).click()
        report = page.locator(".sd-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("ods.user_info")
        browser.close()


@pytest.mark.uitest
def test_schemadrift_paste_drop_and_widen(page_url):
    """SDF2: dropped column + widened type both reported."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_placeholder("Paste the old CREATE TABLE script…").fill(OLD_DDL)
        page.get_by_placeholder("Paste the new CREATE TABLE script…").fill(NEW_DDL)
        page.get_by_role("button", name="Compare", exact=True).click()

        report = page.locator(".sd-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("phone")
        expect(report).to_contain_text("DECIMAL(16")
        browser.close()


@pytest.mark.uitest
def test_schemadrift_identical_no_drift(page_url):
    """SDF3: identical schemas report no drift, no traceback."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_placeholder("Paste the old CREATE TABLE script…").fill(OLD_DDL)
        page.get_by_placeholder("Paste the new CREATE TABLE script…").fill(OLD_DDL)
        page.get_by_role("button", name="Compare", exact=True).click()

        report = page.locator(".sd-report")
        expect(report).to_be_visible(timeout=15000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_schemadrift_suspected_rename(page_url):
    """SDF4: dropped+added column pair flagged as a suspected rename."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_placeholder("Paste the old CREATE TABLE script…").fill(RENAME_OLD)
        page.get_by_placeholder("Paste the new CREATE TABLE script…").fill(RENAME_NEW)
        page.get_by_role("button", name="Compare", exact=True).click()

        report = page.locator(".sd-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("user_real_name")
        browser.close()


@pytest.mark.uitest
def test_schemadrift_bad_path_warning(page_url):
    """SDF5: non-existent path shows the localized bad_path warning."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("summary").click()
        page.get_by_text("Old directory / file").locator(
            "xpath=following-sibling::input").fill(
            str(DEMO / "no_such_dir"))
        page.get_by_role("button", name="Compare directories",
                         exact=True).click()
        expect(page.get_by_text("Path does not exist", exact=False)).to_be_visible(
            timeout=10000)
        browser.close()


@pytest.mark.uitest
def test_schemadrift_empty_input_warnings(page_url):
    """Empty DDL / empty paths show the localized prompts."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Compare", exact=True).click()
        expect(page.get_by_text("Paste both DDL scripts first.",
                                exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_schemadrift_lang_switch(page_url):
    """st-lang cookie drives chrome + server report language."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        expect(page.get_by_role("button", name="对比",
                                exact=True)).to_be_visible()
        page.locator("summary").click()
        page.get_by_role("button", name="对比目录", exact=True).click()
        expect(page.locator(".sd-report")).to_contain_text(
            "破坏", timeout=15000)
        browser.close()


@pytest.mark.uitest
def test_schemadrift_dialect_switch_spark(page_url):
    """Ticket 05: non-default dialect (spark) still compares pasted DDL
    and reports the dropped column."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        def run():
            page.get_by_placeholder(
                "Paste the old CREATE TABLE script…").fill(OLD_DDL)
            page.get_by_placeholder(
                "Paste the new CREATE TABLE script…").fill(NEW_DDL)
            page.get_by_role("button", name="Compare", exact=True).click()

        assert_dialect_switch(page, dialect="spark", run=run,
                              report=page.locator(".sd-report"),
                              contains="phone")
        browser.close()
