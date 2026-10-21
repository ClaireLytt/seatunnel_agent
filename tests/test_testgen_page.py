"""Browser tests for the React /testgen page (ticket 02).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_sqlfmt_page.py. Deselected by default (needs a browser +
built dist):

    pytest -m uitest tests/test_testgen_page.py

Equivalence coverage for the retired uitest YAML cases (cases/testgen.yaml,
removed in this ticket): TGN1 prefilled JOIN generates + validates, TGN2
WHERE literals land in the data, TGN3 DDL column types, TGN4 invalid SQL
without traceback, TGN5 validation off, TGN6 English chrome.
"""

from __future__ import annotations

import pytest

from tests.conftest import assert_dialect_switch, make_page_url

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.sql_testgen.manifest import MANIFEST

page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.sql_testgen.api:router", "/testgen")


@pytest.mark.uitest
def test_testgen_page_smoke(page_url):
    """TGN6-adjacent: English chrome, demo prefill, controls; no console
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
                                name="SQL Test Data Generator")).to_be_visible()
        # demo SQL prefilled (legacy _DEMO_SQL)
        expect(page.locator("textarea").first).to_contain_text("")
        assert "dwd.user_info" in page.locator("textarea").first.input_value()
        expect(page.locator("select")).to_have_value("hive")
        expect(page.locator('input[type="range"]')).to_have_value("5")
        expect(page.locator('input[type="checkbox"]')).to_be_checked()
        expect(page.get_by_role("button", name="Generate",
                                exact=True)).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_testgen_prefilled_join_generates_and_validates(page_url):
    """TGN1: the prefilled JOIN generates both tables and passes SQLite
    validation."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Generate", exact=True).click()
        report = page.locator(".tg-report")
        expect(report).to_be_visible(timeout=10000)
        expect(report).to_contain_text("dwd.user_info")
        expect(report).to_contain_text("dwd.order_pay")
        expect(report).to_contain_text("query executed")  # validation ran
        browser.close()


@pytest.mark.uitest
def test_testgen_where_literals_in_data(page_url):
    """TGN2: WHERE literals (2024-01-01 / PAID) appear in the generated
    rows."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_role("button", name="Generate", exact=True).click()
        report = page.locator(".tg-report")
        expect(report).to_contain_text("2024-01-01")
        expect(report).to_contain_text("PAID")
        browser.close()


@pytest.mark.uitest
def test_testgen_ddl_column_types(page_url):
    """TGN3: pasted DDL drives exact column types (report marks DDL
    columns)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").first.fill("SELECT id, name FROM demo_t")
        page.locator("textarea").nth(1).fill(
            "CREATE TABLE demo_t (id BIGINT, name STRING)")
        page.get_by_role("button", name="Generate", exact=True).click()

        report = page.locator(".tg-report")
        expect(report).to_be_visible(timeout=10000)
        expect(report).to_contain_text("DDL 2")
        browser.close()


@pytest.mark.uitest
def test_testgen_invalid_sql_no_traceback(page_url):
    """TGN4: invalid SQL reports a parse failure, never a traceback."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").first.fill("SELEC FROM WHERE;;")
        page.get_by_role("button", name="Generate", exact=True).click()

        body = page.locator("body")
        expect(page.locator(".tg-report, main")
               .first).to_be_visible(timeout=10000)
        expect(body).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_testgen_validation_off(page_url):
    """TGN5: unchecking SQLite validation drops the execution section."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator('input[type="checkbox"]').uncheck()
        page.get_by_role("button", name="Generate", exact=True).click()

        report = page.locator(".tg-report")
        expect(report).to_be_visible(timeout=10000)
        expect(report).not_to_contain_text("query executed")
        browser.close()


@pytest.mark.uitest
def test_testgen_empty_sql_warning(page_url):
    """Clearing the SQL and generating shows the localized empty warning."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").first.fill("")
        page.get_by_role("button", name="Generate", exact=True).click()
        expect(page.get_by_text("Paste a query first.")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_testgen_lang_switch(page_url):
    """st-lang cookie drives the chrome language, and the report follows."""
    from urllib.parse import urlparse

    from playwright.sync_api import expect, sync_playwright

    host = urlparse(page_url).hostname

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        ctx.add_cookies([{"name": "st-lang", "value": "zh-CN",
                          "domain": host, "path": "/"}])
        page = ctx.new_page()
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("button", name="生成测试数据",
                                exact=True)).to_be_visible()
        page.get_by_role("button", name="生成测试数据", exact=True).click()
        expect(page.locator(".tg-report")).to_contain_text("查询执行成功")
        browser.close()


@pytest.mark.uitest
def test_testgen_dialect_switch_spark(page_url):
    """Ticket 05: non-default dialect (spark) still generates for the
    prefilled JOIN."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        assert_dialect_switch(
            page, dialect="spark",
            run=lambda: page.get_by_role("button", name="Generate",
                                         exact=True).click(),
            report=page.locator(".tg-report"),
            contains="dwd.user_info", timeout=10000)
        browser.close()


@pytest.mark.uitest
def test_testgen_rows_slider_non_default(page_url):
    """Ticket 05: a non-default row-count slider value changes the
    generated row count (report stats line follows the slider)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator('input[type="range"]').fill("8")
        expect(page.locator('input[type="range"]')).to_have_value("8")
        page.get_by_role("button", name="Generate", exact=True).click()

        report = page.locator(".tg-report")
        expect(report).to_be_visible(timeout=10000)
        expect(report).to_contain_text("rows per table 8")
        expect(report).not_to_contain_text("rows per table 5")
        browser.close()
