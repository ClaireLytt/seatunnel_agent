"""Browser tests for the React /migrate page (ticket 04).

Serves the built dist + API router in-process (uvicorn thread), modeled
on tests/test_datacompare_page.py. Deselected by default (needs a
browser + built dist):

    pytest -m uitest tests/test_config_migrate_page.py

Equivalence coverage for the retired uitest YAML cases (cases/migrate.yaml,
removed in ticket 03): MIG1 DataX JSON single migrate, MIG2 sqoop import,
MIG3 batch directory stats, MIG4 unrecognized input does not crash.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_page_url
from tests.conftest import zh_page as _zh_page

pytestmark = pytest.mark.uitest

from seatunnel_agent.agents.data.config_migrate.manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "examples" / "migrate_demo"

DATAX_JOB = (
    '{"job":{"setting":{"speed":{"channel":2}},"content":[{"reader":'
    '{"name":"mysqlreader","parameter":{"username":"u","password":"p",'
    '"column":["a","b"],"connection":[{"table":["t1"],'
    '"jdbcUrl":["jdbc:mysql://h:3306/db"]}]}},'
    '"writer":{"name":"streamwriter","parameter":{}}}]}}'
)
SQOOP_CMD = ("sqoop import --connect jdbc:mysql://h:3306/db --username u "
             "--password p --table orders --target-dir /tmp/out -m 3")


page_url = make_page_url(
    MANIFEST, "seatunnel_agent.agents.data.config_migrate.api:router",
    "/migrate")


@pytest.mark.uitest
def test_config_migrate_page_smoke(page_url):
    """Page loads: heading, input form, batch accordion; no console errors."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text)
                if m.type == "error" else None)
        page.goto(page_url, wait_until="networkidle")

        expect(page.get_by_role("heading",
                                name="DataX/Sqoop → SeaTunnel")).to_be_visible()
        expect(page.locator("textarea")).to_be_visible()
        expect(page.get_by_role("button", name="Migrate",
                                exact=True)).to_be_visible()
        # batch accordion collapsed by default; its fields appear on open
        expect(page.get_by_text("Batch migrate a directory")).to_be_visible()

        assert not console_errors, f"console errors: {console_errors}"
        browser.close()


@pytest.mark.uitest
def test_config_migrate_datax_single(page_url):
    """MIG1: DataX JSON → SeaTunnel conf (query/Console/parallelism) + report."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").fill(DATAX_JOB)
        page.get_by_role("button", name="Migrate", exact=True).click()

        conf = page.locator("pre").first
        expect(conf).to_be_visible()
        expect(conf).to_contain_text("select a, b from t1")
        expect(conf).to_contain_text("Console")
        expect(conf).to_contain_text("parallelism = 2")
        # report rendered below the conf
        expect(page.locator(".cm-report")).to_contain_text(
            "DataX/Sqoop → SeaTunnel Migration")
        browser.close()


@pytest.mark.uitest
def test_config_migrate_sqoop_import(page_url):
    """MIG2: sqoop import → Jdbc source + HdfsFile sink."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").fill(SQOOP_CMD)
        page.get_by_role("button", name="Migrate", exact=True).click()

        conf = page.locator("pre").first
        expect(conf).to_contain_text("HdfsFile")
        expect(conf).to_contain_text("select * from orders")
        browser.close()


@pytest.mark.uitest
def test_config_migrate_batch_directory(page_url):
    """MIG3: batch accordion form migrates the demo dir; stats + notes in report."""
    from playwright.sync_api import expect, sync_playwright

    assert DEMO_DIR.is_dir(), f"demo dir missing: {DEMO_DIR}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.get_by_text("Batch migrate a directory").click()
        page.get_by_placeholder(
            "Directory with *.json / sqoop scripts (recursive)").fill(str(DEMO_DIR))
        page.get_by_role("button", name="Batch migrate", exact=True).click()

        report = page.locator(".cm-report")
        expect(report).to_be_visible()
        # demo dir = 4 jobs, 3 ok / 1 failed (unsupported mongodbreader)
        expect(report).to_contain_text("ok 3")
        expect(report).to_contain_text("failed 1")
        expect(report).to_contain_text("mongodbreader")
        browser.close()


@pytest.mark.uitest
def test_config_migrate_unrecognized_input(page_url):
    """MIG4: unrecognized text yields a readable note, no crash/traceback."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").fill("SELECT 1")
        page.get_by_role("button", name="Migrate", exact=True).click()

        report = page.locator(".cm-report")
        expect(report).to_contain_text("Unrecognized file")
        body = page.locator("body")
        expect(body).not_to_contain_text("Traceback")
        browser.close()


@pytest.mark.uitest
def test_config_migrate_batch_bad_dir_zh(page_url):
    """Batch with a non-directory path shows the localized bad_dir error."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = _zh_page(browser.new_context, page_url)

        page.get_by_text("批量迁移目录").click()
        page.get_by_placeholder("包含 *.json / sqoop 脚本的目录（递归）").fill(
            str(ROOT / "no_such_dir_xyz"))
        page.get_by_role("button", name="批量迁移", exact=True).click()

        expect(page.get_by_text("不是有效目录")).to_be_visible()
        expect(page.get_by_text("no_such_dir_xyz")).to_be_visible()
        browser.close()


@pytest.mark.uitest
def test_config_migrate_lang_switch(page_url):
    """st-lang cookie drives the chrome language (shared lang.ts), and the
    report follows the UI language through the API lang parameter."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # default (no cookie) → English chrome
        page = browser.new_page()
        page.goto(page_url, wait_until="networkidle")
        expect(page.get_by_role("button", name="Migrate",
                                exact=True)).to_be_visible()

        # st-lang=zh-CN cookie (set by the hub) → Chinese chrome + zh report
        zh_page = _zh_page(browser.new_context, page_url)
        expect(zh_page.get_by_role("button", name="迁移",
                                   exact=True)).to_be_visible()
        expect(zh_page.locator("textarea")).to_have_attribute(
            "placeholder", "粘贴 DataX job json，或如 sqoop import --connect …")

        zh_page.locator("textarea").fill("SELECT 1")
        zh_page.get_by_role("button", name="迁移", exact=True).click()
        expect(zh_page.locator(".cm-report")).to_contain_text("无法识别的文件格式")
        browser.close()


@pytest.mark.uitest
def test_config_migrate_copy_conf_clipboard(page_url):
    """Ticket 01: the Copy button writes the generated SeaTunnel config to
    the clipboard (clipboard-read/clipboard-write permissions + readText)."""
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            permissions=["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        page.goto(page_url, wait_until="networkidle")

        page.locator("textarea").fill(DATAX_JOB)
        page.get_by_role("button", name="Migrate", exact=True).click()
        expect(page.locator("pre").first).to_be_visible()

        page.get_by_role("button", name="Copy", exact=True).click()
        expect(page.get_by_text("Copied", exact=False)).to_be_visible()

        clipboard = page.evaluate("() => navigator.clipboard.readText()")
        # clipboard holds the generated config, not the displayed highlight
        assert "select a, b from t1" in clipboard
        assert "Console" in clipboard
        assert "parallelism = 2" in clipboard
        browser.close()
