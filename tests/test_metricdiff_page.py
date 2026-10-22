"""Browser tests for the React /metricdiff page (ticket 02).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_schemadrift_page.py. Deselected by default:

    pytest -m uitest tests/test_metricdiff_page.py

Equivalence coverage for the retired uitest YAML cases
(cases/metricdiff.yaml MDF1-MDF5, removed in this ticket): gmv formula
conflict, source conflict + count normalization non-report, conflict
citing the defining files, bad dir warning, English flow.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import assert_dialect_switch, make_page_url
from tests.conftest import zh_page as _zh_page

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.metric_diff.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "metricdiff_demo"

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.metric_diff.api:router",
    "/metricdiff", chdir="root",
    env={"METRICDIFF_API_ALLOWED_DIRS": str(DEMO)})


@pytest.mark.uitest
def test_metricdiff_page_smoke(page_url):
    """MDF5-adjacent: English chrome + demo prefill; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="Metric Consistency Check")).to_be_visible()
        assert page.locator("input").input_value() == "examples/metricdiff_demo"
        expect(page.locator("select")).to_have_value("hive")
        expect(page.get_by_role("button", name="Check metrics",
                                exact=True)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_metricdiff_formula_and_source_conflicts(page_url):
    """MDF1+MDF2+MDF3: demo dir reports the gmv formula conflict and the
    contact source conflict, citing the defining files; count(1)/count(*)
    normalization does not flag."""
    from playwright.sync_api import expect, sync_playwright

    assert DEMO.is_dir(), f"demo dir missing: {DEMO}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Check metrics", exact=True).click()
        report = page.locator(".md-report")
        expect(report).to_be_visible(timeout=15000)
        expect(report).to_contain_text("gmv")
        expect(report).to_contain_text("different formulas")
        expect(report).to_contain_text("01_gmv_report_a.sql")
        expect(report).to_contain_text("02_gmv_report_b.sql")
        # MDF2 source conflict: contact copied from different source columns
        expect(report).to_contain_text("different source columns")
        expect(report).to_contain_text("contact")
        # normalized count(1)/count(*) metric must NOT be flagged
        expect(report).not_to_contain_text("order_cnt")
        browser.close()


@pytest.mark.uitest
def test_metricdiff_bad_dir_warning(page_url):
    """MDF4: non-directory path shows the localized bad_dir warning."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("input").fill(str(DEMO / "no_such_dir"))
        page.get_by_role("button", name="Check metrics", exact=True).click()
        expect(page.get_by_text("Not a directory", exact=False)).to_be_visible(
            timeout=10000)
        expect(page.locator("body")).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_metricdiff_empty_dir_warning(page_url):
    """Empty directory input shows the localized prompt."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("input").fill("")
        page.get_by_role("button", name="Check metrics", exact=True).click()
        expect(page.get_by_text("Provide a SQL directory first.",
                                exact=False)).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_metricdiff_lang_switch(page_url):
    """st-lang cookie drives chrome + server report language."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        expect(page.get_by_role("button", name="检查口径",
                                exact=True)).to_be_visible()
        page.get_by_role("button", name="检查口径", exact=True).click()
        expect(page.locator(".md-report")).to_contain_text(
            "计算公式不同", timeout=15000)
        browser.close()


@pytest.mark.uitest
def test_metricdiff_dialect_switch_spark(page_url):
    """Ticket 05: non-default dialect (spark) still reports the gmv
    formula conflict on the demo dir."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        assert_dialect_switch(
            page, dialect="spark",
            run=lambda: page.get_by_role("button", name="Check metrics",
                                         exact=True).click(),
            report=page.locator(".md-report"), contains="gmv")
        browser.close()
